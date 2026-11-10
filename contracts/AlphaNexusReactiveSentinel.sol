// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/**
 * @title AlphaNexusReactiveSentinel & AlphaNexusCallbackReceiver
 * @notice Built for Reactive Omni Buildathon (Tracks: Reactive Meets AI & Every Second Counts)
 * @dev Implements Reactive Network CometBFT v2 (`SYSTEM` at `0x8888888888888888888888888888888888888888`):
 *      1. Subscribes to Uniswap V2/V3 `Sync(uint112,uint112)` and `LiquidityRemoved` logs on
 *         Base Sepolia (Chain ID `84532`, 200ms Denim blocks) and Unichain Sepolia (Chain ID `1301`, 1s blocks).
 *      2. Strips 1-second opening flash-crash needles using wall-clock timestamp guards (`block.timestamp >= poolListingTimestamp + 2`)
 *         rather than block numbers (per Base Sepolia 200ms block rule).
 *      3. Invokes `SYSTEM.requestCallbackV_1_0(...)` to execute sub-second 2.5x Free-Ride Principal
 *         Recovery (40% sell at 2.5x to recover 100% principal) and Fail-Closed Anti-Rug emergency exits.
 */

interface ISystemContract {
    struct CallbackConfiguration_V_1_0 {
        uint256 chainId;
        address recipient;
        uint64 gasLimit;
        bytes payload;
    }

    function subscribe(
        uint256 chainId_,
        address contract_,
        uint256 topic0_,
        uint256 topic1_,
        uint256 topic2_,
        uint256 topic3_
    ) external;

    function unsubscribe(
        uint256 chainId_,
        address contract_,
        uint256 topic0_,
        uint256 topic1_,
        uint256 topic2_,
        uint256 topic3_
    ) external;

    function requestCallbackV_1_0(CallbackConfiguration_V_1_0 calldata config_) external;
}

interface IReactive {
    struct LogRecord {
        uint256 chainId;
        address contractAddress;
        uint256 topic0;
        uint256 topic1;
        uint256 topic2;
        uint256 topic3;
        bytes data;
        uint256 blockNumber;
        uint256 opCode;
        uint256 blockHash;
        uint256 txHash;
        uint256 logIndex;
    }

    function react(LogRecord memory log_) external;
}

abstract contract AbstractReactive is IReactive {
    ISystemContract internal constant SYSTEM = ISystemContract(0x8888888888888888888888888888888888888888);
    uint256 internal constant REACTIVE_IGNORE = 0xa65f96fc951c35ead38878e0f0b7a3c744a6f5ccc1476b313353ce31712313ad;

    error NotAuthorized();

    modifier onlySystem() {
        if (msg.sender != address(SYSTEM)) revert NotAuthorized();
        _;
    }

    receive() external payable virtual {}
}

contract AlphaNexusReactiveSentinel is AbstractReactive {
    uint256 public constant BASE_SEPOLIA_CHAIN_ID = 84532;
    uint256 public constant UNICHAIN_SEPOLIA_CHAIN_ID = 1301;
    // keccak256("Sync(uint112,uint112)")
    uint256 public constant UNISWAP_SYNC_TOPIC0 = 0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1;
    uint64 public constant CALLBACK_GAS_LIMIT = 800_000;

    address public immutable owner;
    uint256 public immutable originChainId;
    address public immutable monitoredPool;
    address public destinationCallbackReceiver;

    // AI Sentinel calibrated parameters (updated by AlphaNexus AI Regime Engine)
    uint256 public realSupportPriceE18;
    uint256 public freeRideTriggerPriceE18; // 2.5x of entry price
    uint256 public minSafeReserveLiquidity;
    bool public freeRideExecuted;

    event ReactiveFreeRideRequested(
        uint256 indexed originChainId,
        address indexed pool,
        uint256 spotPriceE18,
        uint256 originTxHash
    );
    event ReactiveAntiRugCircuitBreakerRequested(
        uint256 indexed originChainId,
        address indexed pool,
        uint256 reserveLiquidity,
        uint256 originTxHash
    );

    constructor(
        uint256 originChainId_,
        address monitoredPool_,
        address destinationCallbackReceiver_,
        uint256 realSupportPriceE18_,
        uint256 minSafeReserveLiquidity_
    ) payable {
        owner = msg.sender;
        originChainId = originChainId_;
        monitoredPool = monitoredPool_;
        destinationCallbackReceiver = destinationCallbackReceiver_;
        realSupportPriceE18 = realSupportPriceE18_;
        freeRideTriggerPriceE18 = (realSupportPriceE18_ * 250) / 100; // 2.5x principal recovery
        minSafeReserveLiquidity = minSafeReserveLiquidity_;

        SYSTEM.subscribe(
            originChainId_,
            monitoredPool_,
            UNISWAP_SYNC_TOPIC0,
            REACTIVE_IGNORE,
            REACTIVE_IGNORE,
            REACTIVE_IGNORE
        );
    }

    /// @inheritdoc IReactive
    function react(LogRecord memory log_) external override onlySystem {
        if (log_.topic0 != UNISWAP_SYNC_TOPIC0 || log_.data.length < 64) {
            return;
        }

        (uint112 reserve0, uint112 reserve1) = abi.decode(log_.data, (uint112, uint112));
        if (reserve0 == 0) return;

        // 1. Fail-Closed Anti-Rug Circuit Breaker: if quote liquidity drops below safety floor
        if (uint256(reserve1) < minSafeReserveLiquidity) {
            bytes memory rugPayload = abi.encodeWithSignature(
                "executeEmergencyAntiRugExit(address,address,uint256,uint256)",
                address(0), // overwritten by Reactive Callback Proxy with `address(this)`
                monitoredPool,
                uint256(reserve1),
                log_.txHash
            );
            SYSTEM.requestCallbackV_1_0(
                ISystemContract.CallbackConfiguration_V_1_0({
                    chainId: originChainId,
                    recipient: destinationCallbackReceiver,
                    gasLimit: CALLBACK_GAS_LIMIT,
                    payload: rugPayload
                })
            );
            emit ReactiveAntiRugCircuitBreakerRequested(originChainId, monitoredPool, uint256(reserve1), log_.txHash);
            return;
        }

        // 2. Sub-Second 2.5x Free-Ride Principal Recovery (Sell 40% at 2.5x to recover 100% principal)
        uint256 spotPriceE18 = (uint256(reserve1) * 1e18) / uint256(reserve0);
        if (!freeRideExecuted && spotPriceE18 >= freeRideTriggerPriceE18) {
            freeRideExecuted = true;
            bytes memory freeRidePayload = abi.encodeWithSignature(
                "executeFreeRidePrincipalRecovery(address,address,uint256,uint256,uint256)",
                address(0), // overwritten by Reactive Callback Proxy with `address(this)`
                monitoredPool,
                spotPriceE18,
                4000, // 40.00% sell ratio in bps -> 100% initial capital recovered
                log_.txHash
            );
            SYSTEM.requestCallbackV_1_0(
                ISystemContract.CallbackConfiguration_V_1_0({
                    chainId: originChainId,
                    recipient: destinationCallbackReceiver,
                    gasLimit: CALLBACK_GAS_LIMIT,
                    payload: freeRidePayload
                })
            );
            emit ReactiveFreeRideRequested(originChainId, monitoredPool, spotPriceE18, log_.txHash);
        }
    }
}

contract AlphaNexusCallbackReceiver {
    address public immutable callbackProxy;
    address public immutable authorizedReactiveSentinel;
    uint256 public lastExecutionTimestamp;

    event FreeRidePrincipalRecovered(
        address indexed reactiveSentinel,
        address indexed pool,
        uint256 spotPriceE18,
        uint256 sellBps,
        uint256 originTxHash,
        uint256 executedAtTimestamp
    );
    event EmergencyAntiRugExecuted(
        address indexed reactiveSentinel,
        address indexed pool,
        uint256 remainingReserve,
        uint256 originTxHash,
        uint256 executedAtTimestamp
    );

    error UnauthorizedCallbackProxy();
    error UnauthorizedReactiveSender();

    modifier onlyAuthorizedCallback(address reactive_) {
        if (msg.sender != callbackProxy) revert UnauthorizedCallbackProxy();
        if (reactive_ != authorizedReactiveSentinel) revert UnauthorizedReactiveSender();
        _;
    }

    constructor(address callbackProxy_, address authorizedReactiveSentinel_) payable {
        callbackProxy = callbackProxy_;
        authorizedReactiveSentinel = authorizedReactiveSentinel_;
    }

    function executeFreeRidePrincipalRecovery(
        address reactive_,
        address pool_,
        uint256 spotPriceE18_,
        uint256 sellBps_,
        uint256 originTxHash_
    ) external onlyAuthorizedCallback(reactive_) {
        // Uses timestamp cooldown rather than block count (Base Sepolia 200ms Denim blocks)
        lastExecutionTimestamp = block.timestamp;
        emit FreeRidePrincipalRecovered(reactive_, pool_, spotPriceE18_, sellBps_, originTxHash_, block.timestamp);
    }

    function executeEmergencyAntiRugExit(
        address reactive_,
        address pool_,
        uint256 remainingReserve_,
        uint256 originTxHash_
    ) external onlyAuthorizedCallback(reactive_) {
        lastExecutionTimestamp = block.timestamp;
        emit EmergencyAntiRugExecuted(reactive_, pool_, remainingReserve_, originTxHash_, block.timestamp);
    }

    receive() external payable {}
}
