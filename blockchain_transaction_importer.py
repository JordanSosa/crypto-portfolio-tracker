"""
Blockchain Transaction Importer
Automatically imports transaction history from blockchain addresses into the transaction tracker
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import sys

try:
    from blockchain_balance_fetcher import BlockchainBalanceFetcher
    from transaction_tracker import TransactionTracker, TransactionType, AccountingMethod
    from portfolio_evaluator import PortfolioEvaluator
    try:
        from constants import COIN_IDS, COINGECKO_BASE_URL, DEFAULT_CURRENCY, API_RETRY_COUNT, API_TIMEOUT
    except ImportError:
        # Fallback constants
        COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
        COIN_IDS = {
            "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple",
            "SOL": "solana", "LINK": "chainlink"
        }
        DEFAULT_CURRENCY = "aud"
        API_RETRY_COUNT = 3
        API_TIMEOUT = 10
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Error importing required modules: {e}")
    IMPORTS_AVAILABLE = False

import requests


def get_historical_price_for_date(
    symbol: str,
    target_date: datetime,
    retry_count: int = 3
) -> Optional[float]:
    """
    Get historical price for a specific date from CoinGecko
    
    Args:
        symbol: Asset symbol (e.g., 'BTC')
        target_date: Date to get price for
        retry_count: Number of retry attempts
        
    Returns:
        Price in AUD for that date, or None if not found
    """
    if symbol.upper() not in COIN_IDS:
        return None
    
    coin_id = COIN_IDS[symbol.upper()]
    
    # CoinGecko historical price endpoint
    # Format: /coins/{id}/history?date={dd-mm-yyyy}
    date_str = target_date.strftime("%d-%m-%Y")
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/history"
    params = {
        "date": date_str,
        "localization": "false"
    }
    
    for attempt in range(retry_count):
        try:
            response = requests.get(url, params=params, timeout=API_TIMEOUT)
            
            if response.status_code == 429:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 5
                    time.sleep(wait_time)
                    continue
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Extract price from market_data
            if "market_data" in data and "current_price" in data["market_data"]:
                prices = data["market_data"]["current_price"]
                if isinstance(prices, dict):
                    # Look for the currency (case insensitive)
                    for currency, price in prices.items():
                        if currency.lower() == DEFAULT_CURRENCY.lower():
                            return float(price)
                elif isinstance(prices, (int, float)):
                    # Sometimes it's just a number
                    return float(prices)
            
            # Debug: log what we got if price not found
            if "market_data" in data:
                print(f"      Debug: market_data keys: {list(data['market_data'].keys())}")
                if "current_price" in data["market_data"]:
                    print(f"      Debug: current_price type: {type(data['market_data']['current_price'])}")
                    print(f"      Debug: current_price value: {data['market_data']['current_price']}")
            
            return None
            
        except Exception as e:
            if attempt < retry_count - 1:
                wait_time = (attempt + 1) * 3
                time.sleep(wait_time)
                continue
            print(f"    Error fetching historical price for {symbol} on {date_str}: {e}")
            return None
    
    return None


def import_bitcoin_transactions(
    address: str,
    tracker: TransactionTracker,
    balance_fetcher: BlockchainBalanceFetcher,
    symbol: str = "BTC",
    limit: int = 100,
    min_confirmations: int = 1,
    skip_existing: bool = True
) -> Dict:
    """
    Import Bitcoin transactions from a blockchain address into the transaction tracker
    
    Args:
        address: Bitcoin address
        tracker: TransactionTracker instance
        balance_fetcher: BlockchainBalanceFetcher instance
        symbol: Asset symbol (default: "BTC")
        limit: Maximum number of transactions to process
        min_confirmations: Minimum confirmations required
        skip_existing: Skip transactions that already exist in tracker
        
    Returns:
        Dictionary with import statistics
    """
    print(f"\nImporting {symbol} transactions from address: {address}")
    print("=" * 80)
    
    # Fetch transaction history
    print(f"Fetching transaction history (limit: {limit})...")
    try:
        transactions = balance_fetcher.fetch_bitcoin_transaction_history(address, limit=limit)
    except Exception as e:
        print(f"    Exception while fetching transactions: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    if not transactions:
        print("    No transactions found or error fetching transactions")
        print("    This could mean:")
        print("      - The address has no transaction history")
        print("      - The API returned an error (check debug output above)")
        print("      - The address format is incorrect")
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    print(f"    Found {len(transactions)} transactions to process")
    
    imported = 0
    skipped = 0
    errors = 0
    
    # Process transactions (oldest first)
    for tx in transactions:
        try:
            # Skip if transaction already exists
            if skip_existing and tx.get('tx_hash') and tracker.transaction_exists(tx['tx_hash']):
                skipped += 1
                continue
            
            # Skip if not enough confirmations
            if tx['confirmations'] < min_confirmations:
                skipped += 1
                continue
            
            # Skip if no timestamp
            if not tx['timestamp']:
                skipped += 1
                continue
            
            amount = abs(tx['amount'])
            is_incoming = tx['amount'] > 0
            
            # Skip zero-amount transactions
            if amount == 0:
                skipped += 1
                continue
            
            # Get historical price for transaction date
            print(f"  Processing transaction {tx['tx_hash'][:16]}... ({tx['timestamp'].strftime('%Y-%m-%d')})")
            print(f"    Amount: {amount:.8f} {symbol}, Type: {'BUY' if is_incoming else 'SELL'}")
            price = get_historical_price_for_date(symbol, tx['timestamp'])
            
            if not price:
                print(f"    Warning: Could not fetch historical price for {symbol} on {tx['timestamp'].strftime('%Y-%m-%d')}")
                print(f"    Skipping transaction (price data required for cost basis calculation)")
                skipped += 1
                continue
            
            # Determine transaction type
            if is_incoming:
                trans_type = TransactionType.BUY
                notes = f"Imported from blockchain - Incoming transaction"
            else:
                trans_type = TransactionType.SELL
                notes = f"Imported from blockchain - Outgoing transaction"
            
            # Record transaction
            tracker.record_transaction(
                symbol=symbol,
                transaction_type=trans_type,
                amount=amount,
                price_per_unit=price,
                fee=tx.get('fee', 0.0),
                exchange="Blockchain",
                transaction_id=tx['tx_hash'],
                notes=notes,
                timestamp=tx['timestamp']
            )
            
            imported += 1
            print(f"    [OK] Imported: {amount:.8f} {symbol} @ ${price:,.2f}")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            errors += 1
            print(f"    [ERROR] Error processing transaction: {e}")
            continue
    
    print("=" * 80)
    print(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")
    
    return {
        'total': len(transactions),
        'imported': imported,
        'skipped': skipped,
        'errors': errors
    }


def import_ethereum_transactions(
    address: str,
    tracker: TransactionTracker,
    balance_fetcher: BlockchainBalanceFetcher,
    symbol: str = "ETH",
    limit: int = 100,
    min_confirmations: int = 1,
    skip_existing: bool = True
) -> Dict:
    """
    Import Ethereum transactions from a blockchain address into the transaction tracker
    
    Args:
        address: Ethereum address
        tracker: TransactionTracker instance
        balance_fetcher: BlockchainBalanceFetcher instance
        symbol: Asset symbol (default: "ETH")
        limit: Maximum number of transactions to process
        min_confirmations: Minimum confirmations required
        skip_existing: Skip transactions that already exist in tracker
        
    Returns:
        Dictionary with import statistics
    """
    print(f"\nImporting {symbol} transactions from address: {address}")
    print("=" * 80)
    
    # Fetch transaction history
    print(f"Fetching transaction history (limit: {limit})...")
    try:
        transactions = balance_fetcher.fetch_ethereum_transaction_history(address, limit=limit)
    except Exception as e:
        print(f"    Exception while fetching transactions: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    if not transactions:
        print("    No transactions found or error fetching transactions")
        print("    This could mean:")
        print("      - The address has no transaction history")
        print("      - The API returned an error (check debug output above)")
        print("      - The Etherscan API key is missing or invalid")
        print("      - The address format is incorrect")
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    print(f"    Found {len(transactions)} transactions to process")
    
    imported = 0
    skipped = 0
    errors = 0
    
    # Process transactions (oldest first)
    for tx in transactions:
        try:
            # Skip if transaction already exists
            if skip_existing and tx.get('tx_hash') and tracker.transaction_exists(tx['tx_hash']):
                skipped += 1
                continue
            
            # Skip if not enough confirmations
            if tx['confirmations'] < min_confirmations:
                skipped += 1
                continue
            
            # Skip if no timestamp
            if not tx['timestamp']:
                skipped += 1
                continue
            
            amount = abs(tx['amount'])
            is_incoming = tx['amount'] > 0
            
            # Skip zero-amount transactions
            if amount == 0:
                skipped += 1
                continue
            
            # Get historical price for transaction date
            print(f"  Processing transaction {tx['tx_hash'][:16]}... ({tx['timestamp'].strftime('%Y-%m-%d')})")
            print(f"    Amount: {amount:.8f} {symbol}, Type: {'BUY' if is_incoming else 'SELL'}")
            price = get_historical_price_for_date(symbol, tx['timestamp'])
            
            if not price:
                print(f"    Warning: Could not fetch historical price for {symbol} on {tx['timestamp'].strftime('%Y-%m-%d')}")
                print(f"    Skipping transaction (price data required for cost basis calculation)")
                skipped += 1
                continue
            
            # Determine transaction type
            if is_incoming:
                trans_type = TransactionType.BUY
                notes = f"Imported from blockchain - Incoming transaction"
            else:
                trans_type = TransactionType.SELL
                notes = f"Imported from blockchain - Outgoing transaction"
            
            # Record transaction
            tracker.record_transaction(
                symbol=symbol,
                transaction_type=trans_type,
                amount=amount,
                price_per_unit=price,
                fee=tx.get('fee', 0.0),
                exchange="Blockchain",
                transaction_id=tx['tx_hash'],
                notes=notes,
                timestamp=tx['timestamp']
            )
            
            imported += 1
            print(f"    [OK] Imported: {amount:.8f} {symbol} @ ${price:,.2f}")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            errors += 1
            print(f"    [ERROR] Error processing transaction: {e}")
            continue
    
    print("=" * 80)
    print(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")
    
    return {
        'total': len(transactions),
        'imported': imported,
        'skipped': skipped,
        'errors': errors
    }


def import_erc20_token_transactions(
    address: str,
    token_contract: str,
    symbol: str,
    decimals: int,
    tracker: TransactionTracker,
    balance_fetcher: BlockchainBalanceFetcher,
    limit: int = 100,
    min_confirmations: int = 1,
    skip_existing: bool = True
) -> Dict:
    """
    Import ERC-20 token transactions from a blockchain address into the transaction tracker
    
    Args:
        address: Ethereum address
        token_contract: ERC-20 token contract address
        symbol: Token symbol (e.g., "LINK")
        decimals: Token decimals
        tracker: TransactionTracker instance
        balance_fetcher: BlockchainBalanceFetcher instance
        limit: Maximum number of transactions to process
        min_confirmations: Minimum confirmations required
        skip_existing: Skip transactions that already exist in tracker
        
    Returns:
        Dictionary with import statistics
    """
    print(f"\nImporting {symbol} (ERC-20) transactions from address: {address}")
    print("=" * 80)
    
    # Fetch token transaction history
    print(f"Fetching {symbol} token transaction history (limit: {limit})...")
    try:
        transactions = balance_fetcher.fetch_erc20_token_transaction_history(
            address=address,
            token_contract=token_contract,
            limit=limit
        )
    except Exception as e:
        print(f"    Exception while fetching transactions: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    if not transactions:
        print("    No token transactions found or error fetching transactions")
        print("    This could mean:")
        print("      - The address has no token transaction history")
        print("      - The API returned an error (check debug output above)")
        print("      - The Etherscan API key is missing or invalid")
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    print(f"    Found {len(transactions)} token transactions to process")
    
    imported = 0
    skipped = 0
    errors = 0
    
    # Process transactions (oldest first)
    for tx in transactions:
        try:
            # Skip if transaction already exists
            if skip_existing and tx.get('tx_hash') and tracker.transaction_exists(tx['tx_hash']):
                skipped += 1
                continue
            
            # Skip if not enough confirmations
            if tx['confirmations'] < min_confirmations:
                skipped += 1
                continue
            
            # Skip if no timestamp
            if not tx['timestamp']:
                skipped += 1
                continue
            
            amount = abs(tx['amount'])
            is_incoming = tx['amount'] > 0
            
            # Skip zero-amount transactions
            if amount == 0:
                skipped += 1
                continue
            
            # Get historical price for transaction date
            print(f"  Processing transaction {tx['tx_hash'][:16]}... ({tx['timestamp'].strftime('%Y-%m-%d')})")
            print(f"    Amount: {amount:.8f} {symbol}, Type: {'BUY' if is_incoming else 'SELL'}")
            price = get_historical_price_for_date(symbol, tx['timestamp'])
            
            if not price:
                print(f"    Warning: Could not fetch historical price for {symbol} on {tx['timestamp'].strftime('%Y-%m-%d')}")
                print(f"    Skipping transaction (price data required for cost basis calculation)")
                skipped += 1
                continue
            
            # Determine transaction type
            if is_incoming:
                trans_type = TransactionType.BUY
                notes = f"Imported from blockchain - ERC-20 token incoming transfer"
            else:
                trans_type = TransactionType.SELL
                notes = f"Imported from blockchain - ERC-20 token outgoing transfer"
            
            # Record transaction
            tracker.record_transaction(
                symbol=symbol,
                transaction_type=trans_type,
                amount=amount,
                price_per_unit=price,
                fee=tx.get('fee', 0.0),
                exchange="Blockchain",
                transaction_id=tx['tx_hash'],
                notes=notes,
                timestamp=tx['timestamp']
            )
            
            imported += 1
            print(f"    [OK] Imported: {amount:.8f} {symbol} @ ${price:,.2f}")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            errors += 1
            print(f"    [ERROR] Error processing transaction: {e}")
            continue
    
    print("=" * 80)
    print(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")
    
    return {
        'total': len(transactions),
        'imported': imported,
        'skipped': skipped,
        'errors': errors
    }


def import_xrp_transactions(
    address: str,
    tracker: TransactionTracker,
    balance_fetcher: BlockchainBalanceFetcher,
    symbol: str = "XRP",
    limit: int = 100,
    min_confirmations: int = 1,
    skip_existing: bool = True
) -> Dict:
    """
    Import XRP transactions from a blockchain address into the transaction tracker
    
    Args:
        address: XRP Ledger address
        tracker: TransactionTracker instance
        balance_fetcher: BlockchainBalanceFetcher instance
        symbol: Asset symbol (default: "XRP")
        limit: Maximum number of transactions to process
        min_confirmations: Minimum confirmations required
        skip_existing: Skip transactions that already exist in tracker
        
    Returns:
        Dictionary with import statistics
    """
    print(f"\nImporting {symbol} transactions from address: {address}")
    print("=" * 80)
    
    # Fetch transaction history
    print(f"Fetching transaction history (limit: {limit})...")
    try:
        transactions = balance_fetcher.fetch_xrp_transaction_history(address, limit=limit)
    except Exception as e:
        print(f"    Exception while fetching transactions: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    if not transactions:
        print("    No transactions found or error fetching transactions")
        print("    This could mean:")
        print("      - The address has no transaction history")
        print("      - The API returned an error (check debug output above)")
        print("      - The address format is incorrect")
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    print(f"    Found {len(transactions)} transactions to process")
    
    imported = 0
    skipped = 0
    errors = 0
    
    # Process transactions (oldest first)
    for tx in transactions:
        try:
            # Skip if transaction already exists
            if skip_existing and tx.get('tx_hash') and tracker.transaction_exists(tx['tx_hash']):
                skipped += 1
                continue
            
            # Skip if not enough confirmations
            if tx['confirmations'] < min_confirmations:
                skipped += 1
                continue
            
            # Skip if no timestamp
            if not tx['timestamp']:
                skipped += 1
                continue
            
            amount = abs(tx['amount'])
            is_incoming = tx['amount'] > 0
            
            # Skip zero-amount transactions
            if amount == 0:
                skipped += 1
                continue
            
            # Get historical price for transaction date
            print(f"  Processing transaction {tx['tx_hash'][:16]}... ({tx['timestamp'].strftime('%Y-%m-%d')})")
            print(f"    Amount: {amount:.8f} {symbol}, Type: {'BUY' if is_incoming else 'SELL'}")
            price = get_historical_price_for_date(symbol, tx['timestamp'])
            
            if not price:
                print(f"    Warning: Could not fetch historical price for {symbol} on {tx['timestamp'].strftime('%Y-%m-%d')}")
                print(f"    Skipping transaction (price data required for cost basis calculation)")
                skipped += 1
                continue
            
            # Determine transaction type
            if is_incoming:
                trans_type = TransactionType.BUY
                notes = f"Imported from blockchain - Incoming payment"
            else:
                trans_type = TransactionType.SELL
                notes = f"Imported from blockchain - Outgoing payment"
            
            # Record transaction
            tracker.record_transaction(
                symbol=symbol,
                transaction_type=trans_type,
                amount=amount,
                price_per_unit=price,
                fee=tx.get('fee', 0.0),
                exchange="Blockchain",
                transaction_id=tx['tx_hash'],
                notes=notes,
                timestamp=tx['timestamp']
            )
            
            imported += 1
            print(f"    [OK] Imported: {amount:.8f} {symbol} @ ${price:,.2f}")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            errors += 1
            print(f"    [ERROR] Error processing transaction: {e}")
            continue
    
    print("=" * 80)
    print(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")
    
    return {
        'total': len(transactions),
        'imported': imported,
        'skipped': skipped,
        'errors': errors
    }


def import_solana_transactions(
    address: str,
    tracker: TransactionTracker,
    balance_fetcher: BlockchainBalanceFetcher,
    symbol: str = "SOL",
    limit: int = 100,
    min_confirmations: int = 1,
    skip_existing: bool = True
) -> Dict:
    """
    Import Solana transactions from a blockchain address into the transaction tracker
    
    Args:
        address: Solana address
        tracker: TransactionTracker instance
        balance_fetcher: BlockchainBalanceFetcher instance
        symbol: Asset symbol (default: "SOL")
        limit: Maximum number of transactions to process
        min_confirmations: Minimum confirmations required
        skip_existing: Skip transactions that already exist in tracker
        
    Returns:
        Dictionary with import statistics
    """
    print(f"\nImporting {symbol} transactions from address: {address}")
    print("=" * 80)
    
    # Fetch transaction history
    print(f"Fetching transaction history (limit: {limit})...")
    try:
        transactions = balance_fetcher.fetch_solana_transaction_history(address, limit=limit)
    except Exception as e:
        print(f"    Exception while fetching transactions: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    if not transactions:
        print("    No transactions found or error fetching transactions")
        print("    This could mean:")
        print("      - The address has no transaction history")
        print("      - The API returned an error (check debug output above)")
        print("      - The address format is incorrect")
        return {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    
    print(f"    Found {len(transactions)} transactions to process")
    
    imported = 0
    skipped = 0
    errors = 0
    
    # Process transactions (oldest first)
    for tx in transactions:
        try:
            # Skip if transaction already exists
            if skip_existing and tx.get('tx_hash') and tracker.transaction_exists(tx['tx_hash']):
                skipped += 1
                continue
            
            # Skip if not enough confirmations
            if tx['confirmations'] < min_confirmations:
                skipped += 1
                continue
            
            # Skip if no timestamp
            if not tx['timestamp']:
                skipped += 1
                continue
            
            amount = abs(tx['amount'])
            is_incoming = tx['amount'] > 0
            
            # Skip zero-amount transactions
            if amount == 0:
                skipped += 1
                continue
            
            # Get historical price for transaction date
            print(f"  Processing transaction {tx['tx_hash'][:16]}... ({tx['timestamp'].strftime('%Y-%m-%d')})")
            print(f"    Amount: {amount:.8f} {symbol}, Type: {'BUY' if is_incoming else 'SELL'}")
            price = get_historical_price_for_date(symbol, tx['timestamp'])
            
            if not price:
                print(f"    Warning: Could not fetch historical price for {symbol} on {tx['timestamp'].strftime('%Y-%m-%d')}")
                print(f"    Skipping transaction (price data required for cost basis calculation)")
                skipped += 1
                continue
            
            # Determine transaction type
            if is_incoming:
                trans_type = TransactionType.BUY
                notes = f"Imported from blockchain - Incoming transaction"
            else:
                trans_type = TransactionType.SELL
                notes = f"Imported from blockchain - Outgoing transaction"
            
            # Record transaction
            tracker.record_transaction(
                symbol=symbol,
                transaction_type=trans_type,
                amount=amount,
                price_per_unit=price,
                fee=tx.get('fee', 0.0),
                exchange="Blockchain",
                transaction_id=tx['tx_hash'],
                notes=notes,
                timestamp=tx['timestamp']
            )
            
            imported += 1
            print(f"    [OK] Imported: {amount:.8f} {symbol} @ ${price:,.2f}")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            errors += 1
            print(f"    [ERROR] Error processing transaction: {e}")
            continue
    
    print("=" * 80)
    print(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")
    
    return {
        'total': len(transactions),
        'imported': imported,
        'skipped': skipped,
        'errors': errors
    }


def import_from_wallet_config(
    wallet_config_path: str = "wallet_config.json",
    db_path: str = "portfolio_history.db",
    limit_per_address: int = 100
) -> Dict:
    """
    Import transactions from all addresses in wallet config
    
    Args:
        wallet_config_path: Path to wallet config file
        db_path: Path to database
        limit_per_address: Maximum transactions to import per address
        
    Returns:
        Dictionary with import statistics
    """
    if not IMPORTS_AVAILABLE:
        print("Error: Required modules not available")
        return {}
    
    import json
    
    # Load wallet config
    try:
        with open(wallet_config_path, 'r') as f:
            wallet_config = json.load(f)
    except Exception as e:
        print(f"Error loading wallet config: {e}")
        return {}
    
    # Initialize components
    balance_fetcher = BlockchainBalanceFetcher(
        etherscan_api_key=wallet_config.get("etherscan_api_key")
    )
    tracker = TransactionTracker(db_path)
    
    results = {}
    
    # Import Bitcoin transactions
    if "btc_xpub" in wallet_config and wallet_config["btc_xpub"]:
        print("\n" + "=" * 80)
        print("IMPORTING BITCOIN TRANSACTIONS FROM XPUB")
        print("=" * 80)
        
        # Derive addresses from xpub
        addresses = balance_fetcher.derive_bitcoin_addresses_from_xpub(
            wallet_config["btc_xpub"],
            num_addresses=50
        )
        
        # Import from each address with balance
        for address in addresses:
            balance = balance_fetcher.fetch_bitcoin_balance_single(address, silent=True)
            if balance and balance > 0:
                result = import_bitcoin_transactions(
                    address=address,
                    tracker=tracker,
                    balance_fetcher=balance_fetcher,
                    symbol="BTC",
                    limit=limit_per_address
                )
                results[f"BTC_{address[:10]}"] = result
    
    # Import from single BTC address if provided
    if "btc_address" in wallet_config and wallet_config["btc_address"]:
        result = import_bitcoin_transactions(
            address=wallet_config["btc_address"],
            tracker=tracker,
            balance_fetcher=balance_fetcher,
            symbol="BTC",
            limit=limit_per_address
        )
        results["BTC_single"] = result
    
    # Import Ethereum transactions
    if "eth_address" in wallet_config and wallet_config["eth_address"]:
        print("\n" + "=" * 80)
        print("IMPORTING ETHEREUM TRANSACTIONS")
        print("=" * 80)
        
        result = import_ethereum_transactions(
            address=wallet_config["eth_address"],
            tracker=tracker,
            balance_fetcher=balance_fetcher,
            symbol="ETH",
            limit=limit_per_address
        )
        results["ETH"] = result
    
    # Import ERC-20 token transactions
    if "erc20_tokens" in wallet_config and wallet_config["erc20_tokens"]:
        print("\n" + "=" * 80)
        print("IMPORTING ERC-20 TOKEN TRANSACTIONS")
        print("=" * 80)
        
        eth_address = wallet_config.get("eth_address")
        if not eth_address:
            print("    Warning: eth_address required for ERC-20 token imports")
        else:
            for token in wallet_config["erc20_tokens"]:
                symbol = token.get("symbol")
                contract = token.get("contract")
                decimals = token.get("decimals", 18)
                
                if not symbol or not contract:
                    print(f"    Warning: Skipping token with missing symbol or contract")
                    continue
                
                result = import_erc20_token_transactions(
                    address=eth_address,
                    token_contract=contract,
                    symbol=symbol,
                    decimals=decimals,
                    tracker=tracker,
                    balance_fetcher=balance_fetcher,
                    limit=limit_per_address
                )
                results[f"{symbol}_ERC20"] = result
    
    # Import XRP transactions
    if "xrp_address" in wallet_config and wallet_config["xrp_address"]:
        print("\n" + "=" * 80)
        print("IMPORTING XRP TRANSACTIONS")
        print("=" * 80)
        
        result = import_xrp_transactions(
            address=wallet_config["xrp_address"],
            tracker=tracker,
            balance_fetcher=balance_fetcher,
            symbol="XRP",
            limit=limit_per_address
        )
        results["XRP"] = result
    
    # Import Solana transactions
    if "sol_address" in wallet_config and wallet_config["sol_address"]:
        print("\n" + "=" * 80)
        print("IMPORTING SOLANA TRANSACTIONS")
        print("=" * 80)
        
        result = import_solana_transactions(
            address=wallet_config["sol_address"],
            tracker=tracker,
            balance_fetcher=balance_fetcher,
            symbol="SOL",
            limit=limit_per_address
        )
        results["SOL"] = result
    
    tracker.close()
    
    # Print summary
    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    total_imported = sum(r.get('imported', 0) for r in results.values())
    total_skipped = sum(r.get('skipped', 0) for r in results.values())
    total_errors = sum(r.get('errors', 0) for r in results.values())
    
    print(f"Total imported: {total_imported}")
    print(f"Total skipped: {total_skipped}")
    print(f"Total errors: {total_errors}")
    
    return results


if __name__ == "__main__":
    print("Blockchain Transaction Importer")
    print("=" * 80)
    print("\nThis script will import transaction history from your wallet addresses")
    print("and automatically calculate cost basis using historical prices.\n")
    
    import_from_wallet_config()

