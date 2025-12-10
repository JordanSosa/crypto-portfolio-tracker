import unittest
import sys
import os

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestCoreImports(unittest.TestCase):
    def test_import_blockchain_fetcher(self):
        """Test that we can import the blockchain fetcher module"""
        try:
            from blockchain_balance_fetcher import BlockchainBalanceFetcher
            # Try to instantiate with no API key (should work but be limited)
            fetcher = BlockchainBalanceFetcher()
            self.assertIsNotNone(fetcher)
        except ImportError as e:
            self.fail(f"Failed to import blockchain_balance_fetcher: {e}")

    def test_import_portfolio_evaluator(self):
        """Test that we can import the portfolio evaluator module"""
        try:
            from portfolio_evaluator import PortfolioEvaluator, Asset
            # Create a dummy portfolio
            portfolio = {
                "BTC": Asset("BTC", "Bitcoin", 1.0, 50000.0, 100.0, 50000.0)
            }
            evaluator = PortfolioEvaluator(portfolio)
            self.assertIsNotNone(evaluator)
        except ImportError as e:
            self.fail(f"Failed to import portfolio_evaluator: {e}")

    def test_import_dashboard_api(self):
        """Test that we can import the dashboard api module"""
        try:
            import dashboard_api
            self.assertIsNotNone(dashboard_api.app)
        except ImportError as e:
            self.fail(f"Failed to import dashboard_api: {e}")

if __name__ == '__main__':
    unittest.main()
