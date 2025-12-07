"""
Blockchain Balance Fetcher
Fetches cryptocurrency balances from blockchain addresses using various APIs
"""

import requests
import json
import time
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime

try:
    from bip32utils import BIP32Key
    from base58 import b58decode
    BIP32_AVAILABLE = True
except ImportError:
    BIP32_AVAILABLE = False


class BlockchainBalanceFetcher:
    """Fetches balances from various blockchain networks"""
    
    def __init__(self, etherscan_api_key: Optional[str] = None):
        """
        Initialize the balance fetcher
        
        Args:
            etherscan_api_key: Optional Etherscan API key for Ethereum/ERC-20 tokens
                              Get one free at https://etherscan.io/apis
        """
        self.etherscan_api_key = etherscan_api_key
        self.etherscan_base_url = "https://api.etherscan.io/api"
        
    def derive_bitcoin_addresses_from_xpub(self, xpub: str, num_addresses: int = 50) -> List[str]:
        """
        Derive Bitcoin addresses from an extended public key (xpub)
        
        Args:
            xpub: Extended public key (xpub, ypub, or zpub)
            num_addresses: Number of addresses to derive and check
            
        Returns:
            List of Bitcoin addresses
        """
        if not BIP32_AVAILABLE:
            print("    Error: bip32utils library not installed. Install with: pip install bip32utils base58")
            return []
        
        addresses = []
        try:
            # Validate xpub format (basic check - will be validated by BIP32Key)
            if len(xpub) < 100 or len(xpub) > 120:
                print(f"    Warning: xpub length seems unusual ({len(xpub)} chars), but attempting to use it...")
            
            # Create BIP32 key from xpub once
            try:
                key = BIP32Key.fromExtendedKey(xpub)
            except Exception as e:
                print(f"    Error creating BIP32 key: {e}")
                return []
            
            # Derive addresses from the external chain (change=0, m/0/i)
            for i in range(num_addresses):
                try:
                    # Derive child key at index i (external chain, change=0)
                    child_key = key.ChildKey(i)
                    # Get address (bip32utils handles address format based on xpub type)
                    addr = child_key.Address()
                    if addr:
                        addresses.append(addr)
                except Exception as e:
                    # If derivation fails, continue to next address
                    continue
            
            return addresses
            
        except Exception as e:
            print(f"    Error deriving addresses from xpub: {e}")
            return []
    
    def fetch_bitcoin_balance_from_xpub(self, xpub: str) -> Optional[float]:
        """
        Fetch total Bitcoin balance from an extended public key by checking all derived addresses
        
        Args:
            xpub: Extended public key (xpub, ypub, or zpub)
            
        Returns:
            Total Bitcoin balance across all addresses
        """
        print(f"    Deriving addresses from xpub...")
        addresses = self.derive_bitcoin_addresses_from_xpub(xpub, num_addresses=50)
        
        if not addresses:
            return None
        
        print(f"    Checking balances for {len(addresses)} addresses (this may take a moment)...")
        total_balance = 0.0
        addresses_with_balance = 0
        consecutive_empty = 0
        max_consecutive_empty = 10  # Stop early if we find 10 empty addresses in a row
        
        # Check balances in batches to avoid overwhelming the API
        batch_size = 5
        for i in range(0, len(addresses), batch_size):
            batch = addresses[i:i+batch_size]
            batch_has_balance = False
            
            for address in batch:
                balance = self.fetch_bitcoin_balance_single(address, silent=True)
                if balance and balance > 0:
                    total_balance += balance
                    addresses_with_balance += 1
                    consecutive_empty = 0
                    batch_has_balance = True
                else:
                    consecutive_empty += 1
            
            # Show progress every 10 addresses
            if (i + batch_size) % 10 == 0:
                print(f"    Checked {min(i + batch_size, len(addresses))}/{len(addresses)} addresses...")
            
            # Stop early if we've found many consecutive empty addresses
            if consecutive_empty >= max_consecutive_empty and addresses_with_balance > 0:
                print(f"    Found {max_consecutive_empty} consecutive empty addresses, stopping early...")
                break
            
            # Small delay between batches to be respectful to the API
            if i + batch_size < len(addresses):
                time.sleep(0.3)
        
        if addresses_with_balance > 0:
            print(f"    Found balance in {addresses_with_balance} address(es): {total_balance:.8f} BTC")
        else:
            print(f"    No balance found in first {len(addresses)} addresses")
        
        return total_balance if total_balance > 0 else 0.0
    
    def fetch_bitcoin_balance_single(self, address: str, silent: bool = False, retry_count: int = 3) -> Optional[float]:
        """Fetch Bitcoin balance from a single address (internal helper with retry logic)"""
        # Try multiple APIs with retry logic
        for attempt in range(retry_count):
            # Try BlockCypher first (usually more reliable for bech32 addresses)
            try:
                url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 2
                        if not silent:
                            print(f"    Rate limit on BlockCypher, waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    # Try blockchain.info as fallback
                    if not silent:
                        print(f"    BlockCypher rate limited, trying blockchain.info...")
                    break
                
                response.raise_for_status()
                data = response.json()
                balance_satoshi = data.get("balance", 0)
                btc_balance = balance_satoshi / 100000000.0
                if not silent and btc_balance > 0:
                    print(f"    Found balance: {btc_balance:.8f} BTC")
                return btc_balance
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    if not silent:
                        print(f"    Error on BlockCypher: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                # Fall through to blockchain.info
                break
        
        # Fallback to blockchain.info
        for attempt in range(retry_count):
            try:
                url = f"https://blockchain.info/q/addressbalance/{address}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 2
                        if not silent:
                            print(f"    Rate limit on blockchain.info, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    if not silent:
                        print(f"    Rate limit exceeded on all APIs. Please wait a minute and try again.")
                    return None
                
                response.raise_for_status()
                satoshis = int(response.text)
                btc_balance = satoshis / 100000000.0
                if not silent and btc_balance > 0:
                    print(f"    Found balance: {btc_balance:.8f} BTC")
                return btc_balance
            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    if not silent:
                        print(f"    Error on blockchain.info: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                if not silent:
                    print(f"    Error fetching balance for address: {address}")
                    print(f"    Last error: {e}")
                return None
        
        return None
    
    def fetch_bitcoin_balance(self, address: str = None, xpub: str = None) -> Optional[float]:
        """
        Fetch Bitcoin balance from either a single address or xpub key
        
        Args:
            address: Single Bitcoin address (optional)
            xpub: Extended public key (xpub, ypub, or zpub) (optional)
            
        Returns:
            Bitcoin balance
        """
        # Prefer specific address if provided (faster and more reliable)
        if address:
            balance = self.fetch_bitcoin_balance_single(address, silent=False)
            # If we got a balance, return it. Otherwise, fall back to xpub if available
            if balance and balance > 0:
                return balance
            # If address returned 0 or None, try xpub as fallback
            if xpub:
                print("    Address showed 0 balance, trying xpub to check all addresses...")
                return self.fetch_bitcoin_balance_from_xpub(xpub)
            return balance
        
        # If no address provided, use xpub
        if xpub:
            return self.fetch_bitcoin_balance_from_xpub(xpub)
        
        return None
    
    def fetch_ethereum_balance(self, address: str) -> Optional[float]:
        """Fetch Ethereum (ETH) balance from address"""
        try:
            if not self.etherscan_api_key or self.etherscan_api_key == "YOUR_ETHERSCAN_API_KEY_HERE":
                print("    Warning: Etherscan API key not provided. Ethereum balance fetching disabled.")
                print("    Get a free API key at https://etherscan.io/apis")
                return None
            
            # Validate address format
            if not address or address == "YOUR_ETHEREUM_ADDRESS_HERE":
                print("    Warning: Ethereum address not configured")
                return None
            
            # Validate Ethereum address format (should start with 0x and be 42 chars)
            if not address.startswith("0x") or len(address) != 42:
                print(f"    Error: Invalid Ethereum address format: {address}")
                print("    Ethereum addresses should start with '0x' and be 42 characters long")
                return None
            
            # Use V2 API (V1 is deprecated)
            # Chain ID 1 = Ethereum Mainnet
            url = "https://api.etherscan.io/v2/api"
            params = {
                "module": "account",
                "action": "balance",
                "address": address,
                "chainid": "1",  # Ethereum mainnet
                "apikey": self.etherscan_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data["status"] == "1":
                # Balance is returned in Wei, convert to ETH
                wei_balance = int(data["result"])
                eth_balance = wei_balance / 1e18
                return eth_balance
            else:
                error_msg = data.get('message', 'Unknown error')
                result = data.get('result', '')
                print(f"    Error: {error_msg}")
                if "Invalid API Key" in error_msg:
                    print("    Your Etherscan API key appears to be invalid. Please check it at https://etherscan.io/apis")
                elif "rate limit" in error_msg.lower():
                    print("    Rate limit exceeded. Please wait a moment and try again.")
                else:
                    print(f"    Address used: {address}")
                    print(f"    Result: {result}")
                return None
                
        except Exception as e:
            print(f"    Error fetching Ethereum balance: {e}")
            if address:
                print(f"    Address used: {address}")
            return None
    
    def fetch_erc20_token_balance(self, address: str, token_contract: str, decimals: int = 18) -> Optional[float]:
        """
        Fetch ERC-20 token balance from Ethereum address
        
        Args:
            address: Ethereum wallet address
            token_contract: Token contract address
            decimals: Token decimals (default 18)
        """
        try:
            if not self.etherscan_api_key or self.etherscan_api_key == "YOUR_ETHERSCAN_API_KEY_HERE":
                return None
            
            # Validate contract address format
            if not token_contract.startswith("0x") or len(token_contract) != 42:
                print(f"    Error: Invalid token contract address format: {token_contract}")
                return None
            
            # Use V2 API for token balance
            # Chain ID 1 = Ethereum Mainnet
            url = "https://api.etherscan.io/v2/api"
            params = {
                "module": "account",
                "action": "tokenbalance",
                "contractaddress": token_contract,
                "address": address,
                "chainid": "1",  # Ethereum mainnet
                "apikey": self.etherscan_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data["status"] == "1":
                token_balance = int(data["result"]) / (10 ** decimals)
                return token_balance
            else:
                # Don't print error for 0 balance (status 0 with result "0" is normal)
                if data.get("result") != "0":
                    error_msg = data.get('message', 'Unknown error')
                    print(f"    Error fetching token balance: {error_msg}")
                return None
                
        except Exception as e:
            print(f"    Error fetching ERC-20 token balance: {e}")
            return None
    
    def fetch_xrp_balance(self, address: str) -> Optional[float]:
        """Fetch XRP balance from XRPL address"""
        try:
            # Using XRPL public API
            url = "https://s1.ripple.com:51234"
            payload = {
                "method": "account_info",
                "params": [{
                    "account": address,
                    "strict": True,
                    "ledger_index": "current",
                    "queue": True
                }]
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and "account_data" in data["result"]:
                # XRP balance is in drops (1 XRP = 1,000,000 drops)
                drops = int(data["result"]["account_data"]["Balance"])
                xrp_balance = drops / 1000000.0
                return xrp_balance
            else:
                return None
                
        except Exception as e:
            print(f"Error fetching XRP balance: {e}")
            return None
    
    def fetch_solana_balance(self, address: str) -> Optional[float]:
        """Fetch SOL balance from Solana address"""
        try:
            # Using Solana public RPC endpoint
            url = "https://api.mainnet-beta.solana.com"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data:
                # SOL balance is in lamports (1 SOL = 1,000,000,000 lamports)
                lamports = data["result"]["value"]
                sol_balance = lamports / 1e9
                return sol_balance
            else:
                return None
                
        except Exception as e:
            print(f"Error fetching Solana balance: {e}")
            return None
    
    def fetch_all_balances(self, wallet_config: Dict, prompt_for_btc: bool = True) -> Dict[str, float]:
        """
        Fetch balances for all configured wallet addresses
        
        Args:
            wallet_config: Dictionary with wallet addresses and token contracts
            
        Returns:
            Dictionary mapping asset symbols to balances
        """
        balances = {}
        
        print("Fetching balances from blockchain...")
        
        # Bitcoin - check config first, then try to fetch, then prompt if needed
        if "btc_balance" in wallet_config and wallet_config["btc_balance"] is not None:
            # Use balance from config (for non-interactive use like API)
            try:
                btc_balance = float(wallet_config["btc_balance"])
                if btc_balance > 0:
                    balances["BTC"] = btc_balance
                    print(f"    BTC: {btc_balance:.8f} (from config)")
            except (ValueError, TypeError):
                print("    Invalid btc_balance in config, trying other methods...")
        
        # If no balance from config, try to fetch from address/xpub
        if "BTC" not in balances:
            btc_balance = None
            if "btc_address" in wallet_config and wallet_config["btc_address"]:
                print("  Fetching Bitcoin balance from address...")
                btc_balance = self.fetch_bitcoin_balance(
                    address=wallet_config["btc_address"],
                    xpub=wallet_config.get("btc_xpub")
                )
            elif "btc_xpub" in wallet_config and wallet_config["btc_xpub"]:
                print("  Fetching Bitcoin balance from xpub...")
                btc_balance = self.fetch_bitcoin_balance(xpub=wallet_config["btc_xpub"])
            
            if btc_balance is not None and btc_balance > 0:
                balances["BTC"] = btc_balance
                print(f"    BTC: {btc_balance:.8f}")
        
        # If still no balance and prompting is enabled, ask user
        if "BTC" not in balances and prompt_for_btc:
            try:
                print("  Bitcoin balance:")
                manual_input = input("    Enter your BTC balance (or press Enter to skip): ").strip()
                if manual_input:
                    try:
                        manual_balance = float(manual_input)
                        if manual_balance > 0:
                            balances["BTC"] = manual_balance
                            print(f"    BTC: {manual_balance:.8f}")
                        else:
                            print("    Invalid balance (must be > 0), skipping BTC")
                    except ValueError:
                        print("    Invalid input, skipping manual BTC entry")
                else:
                    print("    Skipping BTC (no balance entered)")
            except (EOFError, KeyboardInterrupt):
                # Handle case where input() is not available (non-interactive mode)
                print("    Skipping manual BTC input (non-interactive mode)")
        
        # Ethereum
        if "eth_address" in wallet_config and wallet_config["eth_address"]:
            print("  Fetching Ethereum balance...")
            eth_balance = self.fetch_ethereum_balance(wallet_config["eth_address"])
            if eth_balance is not None:
                balances["ETH"] = eth_balance
                print(f"    ETH: {eth_balance:.6f}")
            
            # ERC-20 tokens
            if "erc20_tokens" in wallet_config:
                for token in wallet_config["erc20_tokens"]:
                    symbol = token["symbol"]
                    contract = token["contract"]
                    decimals = token.get("decimals", 18)
                    print(f"  Fetching {symbol} balance...")
                    token_balance = self.fetch_erc20_token_balance(
                        wallet_config["eth_address"], 
                        contract, 
                        decimals
                    )
                    if token_balance is not None:
                        balances[symbol] = token_balance
                        print(f"    {symbol}: {token_balance:.6f}")
        
        # XRP
        if "xrp_address" in wallet_config and wallet_config["xrp_address"]:
            print("  Fetching XRP balance...")
            xrp_balance = self.fetch_xrp_balance(wallet_config["xrp_address"])
            if xrp_balance is not None:
                balances["XRP"] = xrp_balance
                print(f"    XRP: {xrp_balance:.6f}")
        
        # Solana
        if "sol_address" in wallet_config and wallet_config["sol_address"]:
            print("  Fetching Solana balance...")
            sol_balance = self.fetch_solana_balance(wallet_config["sol_address"])
            if sol_balance is not None:
                balances["SOL"] = sol_balance
                print(f"    SOL: {sol_balance:.6f}")
        
        print(f"\nSuccessfully fetched {len(balances)} asset balances\n")
        return balances
    
    def fetch_bitcoin_transaction_history(
        self,
        address: str,
        limit: int = 50,
        retry_count: int = 3
    ) -> List[Dict]:
        """
        Fetch Bitcoin transaction history from an address
        
        Args:
            address: Bitcoin address
            limit: Maximum number of transactions to return
            retry_count: Number of retry attempts
            
        Returns:
            List of transaction dictionaries with keys:
            - tx_hash: Transaction hash
            - timestamp: Transaction timestamp (datetime)
            - amount: Amount in BTC (positive for incoming, negative for outgoing)
            - fee: Transaction fee in BTC
            - confirmations: Number of confirmations
        """
        transactions = []
        
        for attempt in range(retry_count):
            try:
                # Use BlockCypher's full address endpoint
                url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/full"
                params = {"limit": limit}
                
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 3
                        print(f"    Rate limit hit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    break
                
                response.raise_for_status()
                data = response.json()
                
                # Process transactions
                for tx in data.get("txs", []):
                    tx_hash = tx.get("hash", "")
                    tx_time = tx.get("confirmed", "")
                    
                    # Parse timestamp
                    timestamp = None
                    if tx_time:
                        try:
                            timestamp = datetime.strptime(tx_time, "%Y-%m-%dT%H:%M:%SZ")
                        except:
                            pass
                    
                    # Calculate net amount for this address
                    # Sum all inputs and outputs involving this address
                    total_input = 0
                    total_output = 0
                    
                    # Check inputs (where BTC came from)
                    for input_tx in tx.get("inputs", []):
                        for addr in input_tx.get("addresses", []):
                            if addr == address:
                                total_input += input_tx.get("output_value", 0) / 100000000.0
                    
                    # Check outputs (where BTC went to)
                    for output in tx.get("outputs", []):
                        for addr in output.get("addresses", []):
                            if addr == address:
                                total_output += output.get("value", 0) / 100000000.0
                    
                    # Net amount: positive if received, negative if sent
                    net_amount = total_output - total_input
                    
                    # Get fee
                    fee_btc = tx.get("fees", 0) / 100000000.0
                    
                    # Get confirmations
                    confirmations = tx.get("confirmations", 0)
                    
                    if net_amount != 0:  # Only include transactions that affected this address
                        transactions.append({
                            'tx_hash': tx_hash,
                            'timestamp': timestamp,
                            'amount': net_amount,
                            'fee': fee_btc,
                            'confirmations': confirmations,
                            'address': address
                        })
                
                # Sort by timestamp (oldest first)
                transactions.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
                return transactions
                
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"    Error fetching transactions: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                print(f"    Error fetching Bitcoin transaction history: {e}")
                return []
        
        return transactions
    
    def fetch_ethereum_transaction_history(
        self,
        address: str,
        limit: int = 50,
        retry_count: int = 3
    ) -> List[Dict]:
        """
        Fetch Ethereum transaction history from an address
        
        Args:
            address: Ethereum address
            limit: Maximum number of transactions to return
            retry_count: Number of retry attempts
            
        Returns:
            List of transaction dictionaries
        """
        if not self.etherscan_api_key:
            print("    Warning: Etherscan API key required for transaction history")
            return []
        
        transactions = []
        
        for attempt in range(retry_count):
            try:
                # Get normal transactions
                url = "https://api.etherscan.io/api"
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": limit,
                    "sort": "asc",  # Oldest first
                    "apikey": self.etherscan_api_key
                }
                
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 3
                        print(f"    Rate limit hit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    break
                
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "1":
                    for tx in data.get("result", []):
                        from_address = tx.get("from", "").lower()
                        to_address = tx.get("to", "").lower()
                        address_lower = address.lower()
                        
                        # Calculate net amount
                        value_wei = int(tx.get("value", "0"))
                        value_eth = value_wei / 1e18
                        
                        # Determine if this is incoming or outgoing
                        if to_address == address_lower:
                            # Incoming transaction
                            amount = value_eth
                        elif from_address == address_lower:
                            # Outgoing transaction
                            amount = -value_eth
                        else:
                            continue  # Not related to this address
                        
                        # Parse timestamp
                        timestamp = None
                        time_stamp = tx.get("timeStamp")
                        if time_stamp:
                            try:
                                timestamp = datetime.fromtimestamp(int(time_stamp))
                            except:
                                pass
                        
                        # Get gas fee (paid by sender)
                        gas_used = int(tx.get("gasUsed", "0"))
                        gas_price = int(tx.get("gasPrice", "0"))
                        fee_eth = (gas_used * gas_price) / 1e18 if from_address == address_lower else 0
                        
                        transactions.append({
                            'tx_hash': tx.get("hash", ""),
                            'timestamp': timestamp,
                            'amount': amount,
                            'fee': fee_eth,
                            'confirmations': int(tx.get("confirmations", "0")),
                            'address': address,
                            'from': from_address,
                            'to': to_address
                        })
                
                # Sort by timestamp
                transactions.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
                return transactions
                
            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"    Error fetching transactions: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                print(f"    Error fetching Ethereum transaction history: {e}")
                return []
        
        return transactions

