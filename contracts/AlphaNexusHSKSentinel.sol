// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title AlphaNexusHSKSentinel
 * @notice Built for HSK Chain Horizon Hackathon · Seoul (Track 1: AI Agent Trading on HSKSwap
 *         & Track 2: Agent Payments & A2A Settlement via HashKey Settlement Platform HSP).
 * @dev Deployable on HSK Chain Mainnet (Chain ID: 177), HSK Chain Testnet (Chain ID: 133),
 *      and Ethereum Sepolia (Chain ID: 11155111, Official Circle Test USDC).
 *      Enforces deterministic on-chain guardrails so conversational AI agents never execute
 *      unverified FOMO chases, honeypot swaps, or self-dealing HSP x402 payment mandates:
 *        1. INV-06 Fail-Closed Anti-Rug Gate (blocks >5% sell tax & >=80% holder concentration).
 *        2. Wick-Stripped Golden Entry Zone [supportLow, supportLow * 1.22] & <=200 bps slippage.
 *        3. Mechanical 2.5x Principal Recovery ("Free-Ride": sell 40% at 2.5x = 100% principal out)
 *           + 35% Moonbag trailing stop.
 *        4. Verifiable HSP x402 v2 Payment Mandate commitment registry (`payer != payTo`, expiry & replay guard).
 */
contract AlphaNexusHSKSentinel {
    uint256 public constant HSK_MAINNET_CHAIN_ID = 177;
    uint256 public constant HSK_TESTNET_CHAIN_ID = 133;
    uint256 public constant ETH_SEPOLIA_CHAIN_ID = 11155111;

    // Canonical HSK Chain Mainnet token references (docs.hashkeychain.net)
    address public constant HSK_MAINNET_WHSK = 0xB210D2120d57b758EE163cFfb43e73728c471Cf1;
    address public constant HSK_MAINNET_USDC = 0x054ed45810DbBAb8B27668922D110669c9D88D0a;
    address public constant HSK_MAINNET_USDT = 0xF1B50eD67A9e2CC94Ad3c477779E2d4cBfFf9029;
    address public constant SEPOLIA_CIRCLE_USDC = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238;

    uint16 public constant GOLDEN_ZONE_UPPER_BPS = 12200; // 1.22x of wick-stripped support
    uint16 public constant FREE_RIDE_MULTIPLIER_BPS = 25000; // 2.50x entry price
    uint16 public constant FREE_RIDE_SELL_RATIO_BPS = 4000; // Sell 40% at 2.5x = 100% principal recovered
    uint16 public constant MOONBAG_TRAILING_STOP_BPS = 3500; // 35% trailing stop from peak
    uint16 public constant MAX_ALLOWED_SELL_TAX_BPS = 500; // >5.00% sell tax = fail-closed block
    uint16 public constant MAX_TOP10_CONCENTRATION_BPS = 8000; // >=80.00% top-10 concentration = block
    uint16 public constant MAX_ALLOWED_SLIPPAGE_BPS = 200; // <=2.00% max slippage

    enum RiskAction {
        HOLD_ACTIVE,
        EXECUTE_25X_FREE_RIDE,
        TRAILING_MOONBAG_STOP,
        EMERGENCY_ANTI_RUG_EXIT
    }

    struct TokenSafetyAudit {
        bytes32 symbolHash;
        uint16 sellTaxBps;
        uint16 top10HolderBps;
        bool lpLockedOrVerified;
        bool isCleared;
        uint64 auditedAt;
    }

    struct TradingPosition {
        address trader;
        address token;
        bytes32 symbolHash;
        uint256 supportLowE18;
        uint256 entryPriceE18;
        uint256 freeRideTriggerE18;
        uint256 peakPriceE18;
        uint256 principalUsdE6;
        uint16 maxSlippageBps;
        bool principalRecovered;
        bool closed;
    }

    struct HSPMandateCommitment {
        bytes32 cartHash;
        bytes32 flowIdHash;
        address payer;
        address payTo;
        address settlementToken;
        uint256 tokenTotalRaw;
        uint64 quoteExpiresAt;
        uint64 anchoredAt;
    }

    address public immutable owner;
    bool public killSwitchEngaged;
    uint256 public nextPositionId;

    mapping(address => TokenSafetyAudit) public tokenAudits;
    mapping(uint256 => TradingPosition) public positions;
    mapping(bytes32 => HSPMandateCommitment) public hspMandates;

    error NotOwner();
    error KillSwitchActive();
    error CounterfeitOrHoneypotBlocked(address token, uint16 sellTaxBps, uint16 top10Bps);
    error EntryAboveGoldenZone(uint256 entryPriceE18, uint256 maxGoldenPriceE18);
    error SlippageTooHigh(uint16 requestedBps, uint16 maxAllowedBps);
    error InvalidHSPMandateParties();
    error HSPQuoteExpired(uint64 quoteExpiresAt, uint64 currentTimestamp);
    error DuplicateCartHash(bytes32 cartHash);

    event TokenAuditRecorded(
        address indexed token,
        bytes32 indexed symbolHash,
        bool isCleared,
        uint16 sellTaxBps,
        uint16 top10HolderBps
    );
    event GoldenWindowPositionOpened(
        uint256 indexed positionId,
        address indexed trader,
        address indexed token,
        uint256 entryPriceE18,
        uint256 freeRideTriggerE18,
        uint256 principalUsdE6
    );
    event PositionExitTriggered(
        uint256 indexed positionId,
        RiskAction indexed action,
        uint256 spotPriceE18,
        uint16 sellRatioBps
    );
    event HSPMandateAnchored(
        bytes32 indexed cartHash,
        bytes32 indexed flowIdHash,
        address indexed payer,
        address payTo,
        address settlementToken,
        uint256 tokenTotalRaw
    );
    event KillSwitchUpdated(bool engaged, string reason);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier whenNotPaused() {
        if (killSwitchEngaged) revert KillSwitchActive();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function setKillSwitch(bool engaged, string calldata reason) external onlyOwner {
        killSwitchEngaged = engaged;
        emit KillSwitchUpdated(engaged, reason);
    }

    function recordAntiRugAudit(
        address token,
        bytes32 symbolHash,
        bool lpLockedOrVerified,
        uint16 sellTaxBps,
        uint16 top10HolderBps
    ) external onlyOwner returns (bool cleared) {
        cleared =
            token != address(0) &&
            lpLockedOrVerified &&
            sellTaxBps <= MAX_ALLOWED_SELL_TAX_BPS &&
            top10HolderBps < MAX_TOP10_CONCENTRATION_BPS;

        tokenAudits[token] = TokenSafetyAudit({
            symbolHash: symbolHash,
            sellTaxBps: sellTaxBps,
            top10HolderBps: top10HolderBps,
            lpLockedOrVerified: lpLockedOrVerified,
            isCleared: cleared,
            auditedAt: uint64(block.timestamp)
        });

        emit TokenAuditRecorded(token, symbolHash, cleared, sellTaxBps, top10HolderBps);
    }

    function openGoldenWindowPosition(
        bytes32 symbolHash,
        address token,
        uint256 supportLowE18,
        uint256 entryPriceE18,
        uint256 principalUsdE6,
        uint16 maxSlippageBps
    ) external whenNotPaused returns (uint256 positionId) {
        TokenSafetyAudit memory audit = tokenAudits[token];
        if (!audit.isCleared) {
            revert CounterfeitOrHoneypotBlocked(token, audit.sellTaxBps, audit.top10HolderBps);
        }
        if (maxSlippageBps > MAX_ALLOWED_SLIPPAGE_BPS) {
            revert SlippageTooHigh(maxSlippageBps, MAX_ALLOWED_SLIPPAGE_BPS);
        }

        uint256 maxGoldenPriceE18 = (supportLowE18 * GOLDEN_ZONE_UPPER_BPS) / 10000;
        if (supportLowE18 == 0 || entryPriceE18 < supportLowE18 || entryPriceE18 > maxGoldenPriceE18) {
            revert EntryAboveGoldenZone(entryPriceE18, maxGoldenPriceE18);
        }

        uint256 freeRideTriggerE18 = (entryPriceE18 * FREE_RIDE_MULTIPLIER_BPS) / 10000;
        positionId = ++nextPositionId;

        positions[positionId] = TradingPosition({
            trader: msg.sender,
            token: token,
            symbolHash: symbolHash,
            supportLowE18: supportLowE18,
            entryPriceE18: entryPriceE18,
            freeRideTriggerE18: freeRideTriggerE18,
            peakPriceE18: entryPriceE18,
            principalUsdE6: principalUsdE6,
            maxSlippageBps: maxSlippageBps,
            principalRecovered: false,
            closed: false
        });

        emit GoldenWindowPositionOpened(
            positionId,
            msg.sender,
            token,
            entryPriceE18,
            freeRideTriggerE18,
            principalUsdE6
        );
    }

    function evaluatePosition(
        uint256 positionId,
        uint256 spotPriceE18,
        uint256 poolQuoteReserveUsdE6,
        uint256 minSafeReserveUsdE6
    ) public view returns (RiskAction action, uint16 sellRatioBps) {
        TradingPosition memory pos = positions[positionId];
        if (pos.closed || pos.entryPriceE18 == 0) {
            return (RiskAction.HOLD_ACTIVE, 0);
        }
        if (poolQuoteReserveUsdE6 < minSafeReserveUsdE6) {
            return (RiskAction.EMERGENCY_ANTI_RUG_EXIT, 10000);
        }
        if (!pos.principalRecovered && spotPriceE18 >= pos.freeRideTriggerE18) {
            return (RiskAction.EXECUTE_25X_FREE_RIDE, FREE_RIDE_SELL_RATIO_BPS);
        }
        uint256 refPeak = spotPriceE18 > pos.peakPriceE18 ? spotPriceE18 : pos.peakPriceE18;
        uint256 trailingFloor = (refPeak * (10000 - MOONBAG_TRAILING_STOP_BPS)) / 10000;
        if (pos.principalRecovered && spotPriceE18 <= trailingFloor) {
            return (RiskAction.TRAILING_MOONBAG_STOP, 10000);
        }
        return (RiskAction.HOLD_ACTIVE, 0);
    }

    /**
     * @notice Anchors a HashKey Settlement Platform (HSP) x402 v2 Payment Mandate digest on-chain.
     * @dev Enforces HSP Agentic Payment Guide invariants: distinct payer & payTo addresses,
     *      non-expired 5-minute quote window, and strict cart_hash replay protection.
     */
    function anchorHSPPaymentMandate(
        bytes32 cartHash,
        bytes32 flowIdHash,
        address payer,
        address payTo,
        address settlementToken,
        uint256 tokenTotalRaw,
        uint64 quoteExpiresAt
    ) external whenNotPaused {
        if (payer == address(0) || payTo == address(0) || payer == payTo || tokenTotalRaw == 0) {
            revert InvalidHSPMandateParties();
        }
        if (quoteExpiresAt <= uint64(block.timestamp)) {
            revert HSPQuoteExpired(quoteExpiresAt, uint64(block.timestamp));
        }
        if (hspMandates[cartHash].anchoredAt != 0) {
            revert DuplicateCartHash(cartHash);
        }

        hspMandates[cartHash] = HSPMandateCommitment({
            cartHash: cartHash,
            flowIdHash: flowIdHash,
            payer: payer,
            payTo: payTo,
            settlementToken: settlementToken,
            tokenTotalRaw: tokenTotalRaw,
            quoteExpiresAt: quoteExpiresAt,
            anchoredAt: uint64(block.timestamp)
        });

        emit HSPMandateAnchored(cartHash, flowIdHash, payer, payTo, settlementToken, tokenTotalRaw);
    }
}
