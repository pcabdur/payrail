# Payment Router

`src/PaymentRouter.sol` transfers the caller's configured USDC-compatible ERC-20 directly to a merchant recipient. It does not custody funds. The contract rejects zero payment IDs, duplicate IDs, zero amounts, the zero recipient, and token addresses other than the configured token. A payment ID is consumed only if the transfer succeeds. The recipient's balance delta must equal the requested amount, so fee-on-transfer behavior reverts.

The deploying account is the OpenZeppelin `Ownable` owner and can update the configured token. Token changes emit `UsdcTokenUpdated`; owner authority and token selection must be managed operationally. The router does not verify whether a configured address is an officially issued USDC contract.

The router takes a `bytes32` payment ID. The API currently maps a public `pi_...` identifier using `keccak256(UTF-8 public_id)` and independently checks the `PaymentReceived` event and router token configuration through a configured Base Sepolia RPC endpoint. A demo browser wallet checkout and ARQ confirmation/reconciliation worker exist. Reorg detection is periodic and does not reverse merchant fulfillment. No deployment or transaction has been performed.

## Install and run tests

Foundry 1.8.6 with solc 0.8.28 and OpenZeppelin Contracts 5.2.0 was used to compile and test this contract locally (8 tests passed). The vendored library is intentionally ignored, so install it after cloning. To repeat from the repository root:

```sh
cd contracts
forge install --no-git OpenZeppelin/openzeppelin-contracts@v5.2.0
forge build --force
forge test --force -vv
```

The Foundry tests use a local mintable six-decimal mock token and do not require a live network, a private key, or `forge-std`. Do not run deployment scripts as part of unit testing.
