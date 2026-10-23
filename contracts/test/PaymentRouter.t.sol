// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {PaymentRouter} from "../src/PaymentRouter.sol";
import {MockERC20} from "./mocks/MockERC20.sol";

interface Vm {
    struct Log {
        bytes32[] topics;
        bytes data;
        address emitter;
    }

    function recordLogs() external;
    function getRecordedLogs() external returns (Log[] memory);
    function prank(address sender) external;
}

contract PaymentRouterTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    MockERC20 private usdc;
    MockERC20 private otherToken;
    PaymentRouter private router;

    address private constant PAYER = address(0xA11CE);
    address private constant MERCHANT = address(0xB0B);
    uint256 private constant AMOUNT = 12_345_678;
    bytes32 private constant PAYMENT_ID = keccak256("payrail-intent-001");

    function setUp() public {
        usdc = new MockERC20("Mock USDC", "USDC");
        otherToken = new MockERC20("Other token", "OTHER");
        router = new PaymentRouter(address(usdc));
        usdc.mint(PAYER, AMOUNT * 3);
    }

    function testPaymentTransfersExactAmountDirectlyAndEmitsEvent() public {
        vm.recordLogs();
        _approve(AMOUNT);

        (bool success,) = _pay(PAYMENT_ID, address(usdc), MERCHANT, AMOUNT);
        require(success, "payment call failed");

        require(usdc.balanceOf(MERCHANT) == AMOUNT, "merchant did not receive exact amount");
        require(usdc.balanceOf(address(router)) == 0, "router must not custody funds");
        require(router.processedPaymentIds(PAYMENT_ID), "payment ID not marked processed");

        Vm.Log[] memory logs = vm.getRecordedLogs();
        bytes32 expectedSignature = keccak256(
            "PaymentReceived(bytes32,address,address,address,uint256)"
        );
        bool found;
        for (uint256 i; i < logs.length; ++i) {
            if (logs[i].emitter != address(router) || logs[i].topics.length != 4) continue;
            if (logs[i].topics[0] != expectedSignature) continue;
            require(logs[i].topics[1] == PAYMENT_ID, "wrong payment ID in event");
            require(address(uint160(uint256(logs[i].topics[2]))) == PAYER, "wrong payer in event");
            require(
                address(uint160(uint256(logs[i].topics[3]))) == MERCHANT,
                "wrong recipient in event"
            );
            (address eventToken, uint256 eventAmount) = abi.decode(logs[i].data, (address, uint256));
            require(eventToken == address(usdc), "wrong token in event");
            require(eventAmount == AMOUNT, "wrong amount in event");
            found = true;
        }
        require(found, "PaymentReceived event missing");
    }

    function testRevertsWithoutApproval() public {
        (bool success, bytes memory result) = _pay(PAYMENT_ID, address(usdc), MERCHANT, AMOUNT);
        require(!success, "transfer unexpectedly succeeded without approval");
        require(result.length > 0, "missing approval should revert with a reason");
        require(!router.processedPaymentIds(PAYMENT_ID), "reverted payment ID was consumed");
        require(usdc.balanceOf(MERCHANT) == 0, "merchant balance changed without approval");
    }

    function testRevertsWhenPaymentIdIsReused() public {
        _approve(AMOUNT * 2);
        (bool firstSuccess,) = _pay(PAYMENT_ID, address(usdc), MERCHANT, AMOUNT);
        require(firstSuccess, "initial payment call failed");

        (bool success,) = _pay(PAYMENT_ID, address(usdc), MERCHANT, AMOUNT);
        require(!success, "duplicate payment ID unexpectedly succeeded");
        require(usdc.balanceOf(MERCHANT) == AMOUNT, "duplicate payment transferred funds");
    }

    function testRevertsForInvalidRecipient() public {
        _approve(AMOUNT);
        (bool success,) = _pay(PAYMENT_ID, address(usdc), address(0), AMOUNT);
        require(!success, "zero recipient unexpectedly succeeded");
    }

    function testRevertsForZeroAmount() public {
        _approve(AMOUNT);
        (bool success,) = _pay(PAYMENT_ID, address(usdc), MERCHANT, 0);
        require(!success, "zero amount unexpectedly succeeded");
    }

    function testRevertsForUnsupportedToken() public {
        otherToken.mint(PAYER, AMOUNT);
        _approveOtherToken(AMOUNT);
        (bool success,) = _pay(PAYMENT_ID, address(otherToken), MERCHANT, AMOUNT);
        require(!success, "unsupported token unexpectedly succeeded");
        require(otherToken.balanceOf(MERCHANT) == 0, "unsupported token was transferred");
    }

    function testOnlyOwnerCanChangeConfiguredToken() public {
        vm.prank(PAYER);
        (bool success,) = address(router).call(
            abi.encodeCall(PaymentRouter.setUsdcToken, (address(otherToken)))
        );
        require(!success, "non-owner changed the configured token");
        require(address(router.usdcToken()) == address(usdc), "configured token changed");
    }

    function testOwnerCanChangeConfiguredToken() public {
        router.setUsdcToken(address(otherToken));
        require(address(router.usdcToken()) == address(otherToken), "owner config was not applied");
    }

    function _approve(uint256 amount) private {
        vm.prank(PAYER);
        usdc.approve(address(router), amount);
    }

    function _approveOtherToken(uint256 amount) private {
        vm.prank(PAYER);
        otherToken.approve(address(router), amount);
    }

    function _pay(bytes32 paymentId, address token, address recipient, uint256 amount)
        private
        returns (bool success, bytes memory result)
    {
        vm.prank(PAYER);
        return address(router).call(
            abi.encodeCall(PaymentRouter.pay, (paymentId, token, recipient, amount))
        );
    }
}
