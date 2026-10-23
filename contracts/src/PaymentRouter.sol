// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// @title PaymentRouter
/// @notice Routes a payer's configured USDC directly to a merchant recipient.
/// @dev Payment IDs are globally unique. The router never holds payment funds.
contract PaymentRouter is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public usdcToken;
    mapping(bytes32 paymentId => bool processed) public processedPaymentIds;

    error ZeroAddress();
    error InvalidPaymentId();
    error PaymentAlreadyProcessed(bytes32 paymentId);
    error UnsupportedToken(address token);
    error ZeroAmount();
    error InvalidRecipient(address recipient);
    error InexactTransfer(uint256 expectedAmount, uint256 receivedAmount);

    event UsdcTokenUpdated(address indexed previousToken, address indexed newToken);
    event PaymentReceived(
        bytes32 indexed paymentId,
        address indexed payer,
        address indexed recipient,
        address token,
        uint256 amount
    );

    /// @param initialUsdcToken The USDC-compatible ERC-20 token accepted by this router.
    constructor(address initialUsdcToken) Ownable(msg.sender) {
        _setUsdcToken(initialUsdcToken);
    }

    /// @notice Change the accepted USDC token. Only the owner can configure the token.
    /// @dev Ownership can be transferred or renounced using OpenZeppelin Ownable.
    function setUsdcToken(address newUsdcToken) external onlyOwner {
        _setUsdcToken(newUsdcToken);
    }

    /// @notice Transfer an exact USDC amount from the caller directly to a merchant.
    /// @param paymentId Unique bytes32 identifier for the payment intent.
    /// @param token Token address; it must match the configured USDC token.
    /// @param recipient Merchant wallet that receives the payment.
    /// @param amount Exact integer token base units to transfer.
    function pay(
        bytes32 paymentId,
        address token,
        address recipient,
        uint256 amount
    ) external nonReentrant {
        if (paymentId == bytes32(0)) revert InvalidPaymentId();
        if (processedPaymentIds[paymentId]) revert PaymentAlreadyProcessed(paymentId);
        if (recipient == address(0)) revert InvalidRecipient(recipient);
        if (amount == 0) revert ZeroAmount();
        if (token != address(usdcToken)) revert UnsupportedToken(token);

        // Mark before the external token call; a failing call reverts this state change.
        processedPaymentIds[paymentId] = true;

        IERC20 paymentToken = IERC20(token);
        uint256 balanceBefore = paymentToken.balanceOf(recipient);
        paymentToken.safeTransferFrom(msg.sender, recipient, amount);
        uint256 receivedAmount = paymentToken.balanceOf(recipient) - balanceBefore;
        if (receivedAmount != amount) revert InexactTransfer(amount, receivedAmount);

        emit PaymentReceived(paymentId, msg.sender, recipient, token, amount);
    }

    function _setUsdcToken(address newUsdcToken) private {
        if (newUsdcToken == address(0)) revert ZeroAddress();
        if (newUsdcToken.code.length == 0) revert UnsupportedToken(newUsdcToken);

        address previousToken = address(usdcToken);
        usdcToken = IERC20(newUsdcToken);
        emit UsdcTokenUpdated(previousToken, newUsdcToken);
    }
}
