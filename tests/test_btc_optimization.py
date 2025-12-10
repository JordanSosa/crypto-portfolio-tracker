import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBtcOptimization(unittest.TestCase):
    def setUp(self):
        try:
            from blockchain_balance_fetcher import BlockchainBalanceFetcher
            self.fetcher = BlockchainBalanceFetcher()
        except ImportError:
            self.fail("Could not import BlockchainBalanceFetcher")

    def test_parallel_fetching_logic(self):
        """Test that fetch_bitcoin_balance_from_xpub correctly sums balances with parallel execution"""
        
        # Mock the dependency methods
        # 1. derive_bitcoin_addresses_from_xpub -> returns 50 fake addresses
        # 2. has_bitcoin_transactions -> returns True for first 2, False for rest
        # 3. fetch_bitcoin_balance_single -> returns 0.5 for active addresses
        
        fake_addresses = [f"addr{i}" for i in range(50)]
        self.fetcher.derive_bitcoin_addresses_from_xpub = MagicMock(return_value=fake_addresses)
        
        # address 0 and 1 have txs
        def mock_has_tx(addr, retry_count=2):
            if addr in ["addr0", "addr1"]:
                return True
            return False
            
        self.fetcher.has_bitcoin_transactions = MagicMock(side_effect=mock_has_tx)
        
        def mock_fetch_balance(addr, silent=False, retry_count=3):
            if addr in ["addr0", "addr1"]:
                return 0.5
            return 0.0
            
        self.fetcher.fetch_bitcoin_balance_single = MagicMock(side_effect=mock_fetch_balance)
        
        # Run the method
        print("Running parallel fetch test...")
        total_balance = self.fetcher.fetch_bitcoin_balance_from_xpub("mock_xpub")
        
        # Verify results
        # We expect 0.5 + 0.5 = 1.0 total
        self.assertEqual(total_balance, 1.0)
        
        # Verify derivation was called
        self.fetcher.derive_bitcoin_addresses_from_xpub.assert_called_once()
        
        # Verify has_bitcoin_transactions was called 50 times (since we submit all)
        # Note: In parallel execution, exact call count assertion on mocks can sometimes be tricky 
        # due to race conditions in recording, but MagicMock usually handles it.
        self.assertEqual(self.fetcher.has_bitcoin_transactions.call_count, 50)
        
        print("Parallel fetch test passed!")

if __name__ == '__main__':
    unittest.main()
