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

# Try pycoin as alternative (for zpub and unsupported xpub formats)
try:
    from pycoin.symbols.btc import network as btc_network
    from pycoin.key.BIP32Node import BIP32Node
    PYCOIN_AVAILABLE = True
except ImportError:
    PYCOIN_AVAILABLE = False


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
        Derive Bitcoin addresses from an extended public key (xpub, ypub, or zpub)
        
        Args:
            xpub: Extended public key (xpub, ypub, or zpub)
            num_addresses: Number of addresses to derive and check
            
        Returns:
            List of Bitcoin addresses
        """
        addresses = []
        xpub_clean = xpub.strip()
        
        # Detect key type
        key_type = "unknown"
        if xpub_clean.startswith("xpub"):
            key_type = "xpub (Legacy)"
        elif xpub_clean.startswith("ypub"):
            key_type = "ypub (SegWit wrapped)"
        elif xpub_clean.startswith("zpub"):
            key_type = "zpub (Native SegWit)"
        
        print(f"    Deriving addresses from {key_type}...")
        
        # Try bip32utils first
        if BIP32_AVAILABLE:
            try:
                key = BIP32Key.fromExtendedKey(xpub_clean)
                print(f"    Successfully parsed with bip32utils")
                
                for i in range(num_addresses):
                    try:
                        child_key = key.ChildKey(i)
                        addr = child_key.Address()
                        if addr:
                            addresses.append(addr)
                            if i < 3:  # Debug first few
                                print(f"      Address {i}: {addr}")
                    except Exception as e:
                        if i < 3:
                            print(f"      Error deriving address {i}: {e}")
                        continue
                
                if addresses:
                    print(f"    Derived {len(addresses)} addresses using bip32utils")
                    return addresses
            except Exception as e:
                error_msg = str(e)
                if "unknown extended key version" in error_msg.lower() or "checksum" in error_msg.lower():
                    print(f"    bip32utils doesn't support this key format: {error_msg}")
                    print(f"    Trying alternative library (pycoin)...")
                else:
                    print(f"    bip32utils failed: {error_msg}")
                    if not PYCOIN_AVAILABLE:
                        return []
        
        # Try pycoin as fallback
        if PYCOIN_AVAILABLE:
            try:
                print(f"    Attempting to use pycoin library...")
                
                key_obj = None
                
                # Method 1: Try using network.parse() directly (works for xpub/ypub/zpub)
                try:
                    key_obj = btc_network.parse(xpub_clean)
                    if key_obj:
                        print(f"    pycoin: Successfully parsed using network.parse()")
                except Exception as e1:
                    # Method 2: Try using network.parse.bip32_pub
                    try:
                        key_obj = btc_network.parse.bip32_pub(xpub_clean)
                        if key_obj:
                            print(f"    pycoin: Successfully parsed using network.parse.bip32_pub")
                    except Exception as e2:
                        # Method 3: Try deserializing from base58
                        try:
                            import base58
                            decoded = base58.b58decode(xpub_clean)
                            key_obj = BIP32Node.deserialize(decoded)
                            if key_obj:
                                print(f"    pycoin: Successfully parsed using BIP32Node.deserialize")
                        except Exception as e3:
                            print(f"    pycoin: Parsing methods failed")
                            print(f"      network.parse(): {e1}")
                            print(f"      network.parse.bip32_pub: {e2}")
                            print(f"      deserialize: {e3}")
                
                if key_obj:
                    print(f"    Deriving {num_addresses} addresses...")
                    for i in range(num_addresses):
                        try:
                            # Try different path formats
                            subkey = None
                            try:
                                subkey = key_obj.subkey_for_path(f"0/{i}")
                            except:
                                try:
                                    subkey = key_obj.subkey_for_path(f"m/0/{i}")
                                except:
                                    try:
                                        # Try with hardened derivation
                                        subkey = key_obj.subkey(0).subkey(i)
                                    except:
                                        pass
                            
                            if subkey:
                                addr = subkey.address()
                                if addr:
                                    addresses.append(addr)
                                    if i < 5:  # Debug first few
                                        print(f"      Address {i}: {addr}")
                        except Exception as e:
                            if i < 3:
                                print(f"      Error deriving address {i}: {e}")
                            continue
                    
                    if addresses:
                        print(f"    Successfully derived {len(addresses)} addresses using pycoin")
                        return addresses
                    else:
                        print(f"    pycoin parsed the key but couldn't derive any addresses")
                else:
                    print(f"    pycoin couldn't parse the extended key")
                    
            except ImportError:
                print(f"    pycoin not available. Install with: pip install pycoin")
            except Exception as e:
                print(f"    pycoin failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            if not BIP32_AVAILABLE:
                print(f"    Error: Neither bip32utils nor pycoin are available.")
                print(f"    Install one with: pip install bip32utils base58")
                print(f"    Or: pip install pycoin")
    
        print(f"    Error: Could not derive addresses from {key_type}")
        print(f"    The key format may not be supported, or the derivation path may be incorrect")
        print(f"    Try using a different key format (xpub/ypub/zpub) or check your wallet's derivation path")
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
                # Accept 0 as valid (not an error)
                if not silent:
                    if btc_balance > 0:
                        print(f"    Found balance: {btc_balance:.8f} BTC")
                    else:
                        print(f"    Address balance: {btc_balance:.8f} BTC")
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
                # Accept 0 as valid (not an error)
                if not silent:
                    if btc_balance > 0:
                        print(f"    Found balance: {btc_balance:.8f} BTC")
                    else:
                        print(f"    Address balance: {btc_balance:.8f} BTC")
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
    
    def fetch_erc20_token_transaction_history(
        self,
        address: str,
        token_contract: str,
        limit: int = 50,
        retry_count: int = 3
    ) -> List[Dict]:
        """
        Fetch ERC-20 token transaction history from an address
        
        Args:
            address: Ethereum address
            token_contract: ERC-20 token contract address
            limit: Maximum number of transactions to return
            retry_count: Number of retry attempts
            
        Returns:
            List of transaction dictionaries
        """
        if not self.etherscan_api_key:
            print("    Warning: Etherscan API key required for token transaction history")
            return []
        
        transactions = []
        
        for attempt in range(retry_count):
            try:
                # Get ERC-20 token transfers using Etherscan API V2
                url = "https://api.etherscan.io/v2/api"
                params = {
                    "module": "account",
                    "action": "tokentx",  # Token transfers
                    "contractaddress": token_contract,
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": limit,
                    "sort": "asc",  # Oldest first
                    "chainid": "1",  # Ethereum Mainnet (required for V2)
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
                
                # Debug: Check Etherscan API response
                print(f"    Debug: Etherscan Token API status: {response.status_code}")
                print(f"    Debug: Etherscan response status field: {data.get('status')}")
                print(f"    Debug: Etherscan response message: {data.get('message', 'N/A')}")
                
                if data.get("status") != "1":
                    error_msg = data.get("message", "Unknown error")
                    result = data.get("result", "")
                    print(f"    Etherscan API error: {error_msg}")
                    if "Invalid API Key" in str(error_msg):
                        print("    Your Etherscan API key may be invalid. Check your config.")
                    elif "rate limit" in str(error_msg).lower() or "Max rate limit" in str(error_msg):
                        print("    Rate limit exceeded. Please wait and try again later.")
                    elif "No transactions found" in str(result) or result == "[]":
                        print("    No token transactions found for this address")
                    else:
                        print(f"    Result: {result[:200] if result else 'N/A'}")
                    return []
                
                result = data.get("result", [])
                if isinstance(result, str):
                    if "rate limit" in result.lower() or "max rate limit" in result.lower():
                        print(f"    Rate limit error in result: {result}")
                        return []
                    result = []
                
                print(f"    Debug: Found {len(result)} token transactions in Etherscan response")
                
                if len(result) > 0 and isinstance(result, list):
                    print(f"    Debug: First transaction keys: {list(result[0].keys()) if isinstance(result[0], dict) else 'N/A'}")
                
                # Process token transfers
                if isinstance(result, list) and len(result) > 0:
                    for tx in result:
                        from_address = tx.get("from", "").lower()
                        to_address = tx.get("to", "").lower()
                        address_lower = address.lower()
                        
                        # Get token amount (value is in smallest unit, need decimals)
                        token_decimals = int(tx.get("tokenDecimal", "18"))
                        value_raw = int(tx.get("value", "0"))
                        token_amount = value_raw / (10 ** token_decimals)
                        
                        # Determine if this is incoming or outgoing
                        if to_address == address_lower:
                            # Incoming token transfer
                            amount = token_amount
                        elif from_address == address_lower:
                            # Outgoing token transfer
                            amount = -token_amount
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
                        
                        # Token transfers don't have gas fees in the same way
                        # The gas was paid in ETH, not tokens
                        fee_token = 0.0
                        
                        transactions.append({
                            'tx_hash': tx.get("hash", ""),
                            'timestamp': timestamp,
                            'amount': amount,
                            'fee': fee_token,
                            'confirmations': int(tx.get("confirmations", "0")),
                            'address': address,
                            'from': from_address,
                            'to': to_address,
                            'token_contract': token_contract,
                            'token_symbol': tx.get("tokenSymbol", ""),
                            'token_decimals': token_decimals
                        })
                
                # Sort by timestamp
                transactions.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
                return transactions
                
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"    Error fetching transactions: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                print(f"    Error fetching ERC-20 token transaction history: {e}")
                if 'response' in locals():
                    print(f"    Response status code: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"    Error response: {error_data}")
                    except:
                        print(f"    Error response text: {response.text[:500]}")
                return []
            except Exception as e:
                print(f"    Unexpected error fetching ERC-20 token transactions: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        return transactions
    
    def fetch_xrp_transaction_history(
        self,
        address: str,
        limit: int = 50,
        retry_count: int = 3
    ) -> List[Dict]:
        """
        Fetch XRP transaction history from an address
        
        Args:
            address: XRP Ledger address
            limit: Maximum number of transactions to return
            retry_count: Number of retry attempts
            
        Returns:
            List of transaction dictionaries
        """
        transactions = []
        
        for attempt in range(retry_count):
            try:
                # Using XRPL public API
                url = "https://s1.ripple.com:51234"
                payload = {
                    "method": "account_tx",
                    "params": [{
                        "account": address,
                        "ledger_index_min": -1,
                        "ledger_index_max": -1,
                        "limit": limit,
                        "binary": False,
                        "forward": False  # Get oldest first
                    }]
                }
                
                response = requests.post(url, json=payload, timeout=15)
                
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 3
                        print(f"    Rate limit hit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    break
                
                response.raise_for_status()
                data = response.json()
                
                # Debug: Check XRPL API response
                print(f"    Debug: XRPL API status: {response.status_code}")
                
                if "result" not in data or data["result"].get("status") != "success":
                    error_msg = data.get("result", {}).get("error", "Unknown error")
                    print(f"    XRPL API error: {error_msg}")
                    return []
                
                tx_list = data["result"].get("transactions", [])
                print(f"    Debug: Found {len(tx_list)} transactions in XRPL response")
                
                if len(tx_list) > 0:
                    print(f"    Debug: First transaction keys: {list(tx_list[0].get('tx', {}).keys()) if tx_list[0].get('tx') else 'N/A'}")
                
                # Process transactions
                for tx_entry in tx_list:
                    tx = tx_entry.get("tx", {})
                    meta = tx_entry.get("meta", {})
                    
                    tx_hash = tx.get("hash", "")
                    tx_type = tx.get("TransactionType", "")
                    
                    # Only process Payment transactions for now
                    if tx_type != "Payment":
                        continue
                    
                    # Get account addresses
                    account = tx.get("Account", "").lower()
                    destination = tx.get("Destination", "").lower()
                    address_lower = address.lower()
                    
                    # Get amount (XRP is in drops, 1 XRP = 1,000,000 drops)
                    amount_str = tx.get("Amount", "0")
                    if isinstance(amount_str, str):
                        # XRP amount in drops
                        try:
                            drops = int(amount_str)
                            xrp_amount = drops / 1000000.0
                        except:
                            continue
                    else:
                        # Could be issued currency (not XRP), skip for now
                        continue
                    
                    # Determine if this is incoming or outgoing
                    if destination == address_lower:
                        # Incoming payment
                        amount = xrp_amount
                    elif account == address_lower:
                        # Outgoing payment
                        amount = -xrp_amount
                    else:
                        continue  # Not related to this address
                    
                    # Get fee (in drops)
                    fee_drops = int(tx.get("Fee", "0"))
                    fee_xrp = fee_drops / 1000000.0
                    
                    # Get timestamp from ledger close time
                    timestamp = None
                    ledger_time = tx.get("date")
                    if ledger_time:
                        try:
                            # XRPL date is seconds since Ripple epoch (2000-01-01)
                            ripple_epoch = 946684800  # Unix timestamp for 2000-01-01
                            unix_timestamp = ripple_epoch + ledger_time
                            timestamp = datetime.fromtimestamp(unix_timestamp)
                        except:
                            pass
                    
                    # Get transaction result
                    transaction_result = meta.get("TransactionResult", "")
                    confirmations = 1 if transaction_result == "tesSUCCESS" else 0
                    
                    transactions.append({
                        'tx_hash': tx_hash,
                        'timestamp': timestamp,
                        'amount': amount,
                        'fee': fee_xrp if account == address_lower else 0.0,  # Fee only for outgoing
                        'confirmations': confirmations,
                        'address': address,
                        'tx_type': tx_type
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
                print(f"    Error fetching XRP transaction history: {e}")
                if 'response' in locals():
                    print(f"    Response status code: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"    Error response: {error_data}")
                    except:
                        print(f"    Error response text: {response.text[:500]}")
                return []
            except Exception as e:
                print(f"    Unexpected error fetching XRP transactions: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        return transactions
    
    def fetch_solana_transaction_history(
        self,
        address: str,
        limit: int = 50,
        retry_count: int = 3
    ) -> List[Dict]:
        """
        Fetch Solana transaction history from an address
        
        Args:
            address: Solana address
            limit: Maximum number of transactions to return
            retry_count: Number of retry attempts
            
        Returns:
            List of transaction dictionaries
        """
        transactions = []
        
        for attempt in range(retry_count):
            try:
                # Using Solana public RPC endpoint
                url = "https://api.mainnet-beta.solana.com"
                
                # Step 1: Get transaction signatures
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [
                        address,
                        {
                            "limit": limit
                        }
                    ]
                }
                
                response = requests.post(url, json=payload, timeout=15)
                
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 3
                        print(f"    Rate limit hit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    break
                
                response.raise_for_status()
                data = response.json()
                
                # Debug: Check Solana API response
                print(f"    Debug: Solana API status: {response.status_code}")
                
                if "error" in data:
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    print(f"    Solana API error: {error_msg}")
                    return []
                
                signatures = data.get("result", [])
                print(f"    Debug: Found {len(signatures)} transaction signatures")
                
                if not signatures:
                    return []
                
                # Step 2: Get full transaction details for each signature
                # Process in batches to avoid overwhelming the API
                batch_size = 10
                for i in range(0, len(signatures), batch_size):
                    batch = signatures[i:i + batch_size]
                    
                    for sig_entry in batch:
                        signature = sig_entry.get("signature")
                        if not signature:
                            continue
                        
                        # Get full transaction
                        tx_payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getTransaction",
                            "params": [
                                signature,
                                {
                                    "encoding": "json",
                                    "maxSupportedTransactionVersion": 0
                                }
                            ]
                        }
                        
                        tx_response = requests.post(url, json=tx_payload, timeout=15)
                        if tx_response.status_code != 200:
                            continue
                        
                        tx_data = tx_response.json()
                        if "error" in tx_data or "result" not in tx_data:
                            continue
                        
                        tx_result = tx_data.get("result")
                        if not tx_result:
                            continue
                        
                        # Parse transaction
                        tx_meta = tx_result.get("meta", {})
                        if tx_meta.get("err"):
                            continue  # Skip failed transactions
                        
                        # Get timestamp
                        block_time = tx_result.get("blockTime")
                        timestamp = None
                        if block_time:
                            try:
                                timestamp = datetime.fromtimestamp(block_time)
                            except:
                                pass
                        
                        # Calculate SOL amount from account balance changes
                        pre_balances = tx_meta.get("preBalances", [])
                        post_balances = tx_meta.get("postBalances", [])
                        account_keys = tx_result.get("transaction", {}).get("message", {}).get("accountKeys", [])
                        
                        # Find our address in the account keys
                        address_index = None
                        for idx, key_info in enumerate(account_keys):
                            if isinstance(key_info, str):
                                if key_info == address:
                                    address_index = idx
                                    break
                            elif isinstance(key_info, dict):
                                if key_info.get("pubkey") == address:
                                    address_index = idx
                                    break
                        
                        if address_index is None or address_index >= len(pre_balances):
                            continue
                        
                        # Calculate balance change (in lamports)
                        pre_balance = pre_balances[address_index] if address_index < len(pre_balances) else 0
                        post_balance = post_balances[address_index] if address_index < len(post_balances) else 0
                        balance_change = post_balance - pre_balance
                        
                        # Convert to SOL (1 SOL = 1,000,000,000 lamports)
                        sol_amount = balance_change / 1e9
                        
                        # Skip zero-amount transactions
                        if abs(sol_amount) < 0.00000001:
                            continue
                        
                        # Get fee (in lamports, paid by signer)
                        fee_lamports = tx_meta.get("fee", 0)
                        fee_sol = fee_lamports / 1e9
                        
                        # Determine if incoming or outgoing
                        # If balance increased, it's incoming (positive)
                        # If balance decreased, it's outgoing (negative)
                        amount = sol_amount
                        
                        transactions.append({
                            'tx_hash': signature,
                            'timestamp': timestamp,
                            'amount': amount,
                            'fee': fee_sol if amount < 0 else 0.0,  # Fee only for outgoing
                            'confirmations': 1,  # Solana transactions are final when included
                            'address': address
                        })
                    
                    # Small delay between batches
                    if i + batch_size < len(signatures):
                        time.sleep(0.5)
                
                # Sort by timestamp (oldest first)
                transactions.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
                return transactions
                
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"    Error fetching transactions: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                print(f"    Error fetching Solana transaction history: {e}")
                if 'response' in locals():
                    print(f"    Response status code: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"    Error response: {error_data}")
                    except:
                        print(f"    Error response text: {response.text[:500]}")
                return []
            except Exception as e:
                print(f"    Unexpected error fetching Solana transactions: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        return transactions
    
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
        
        # Bitcoin - prioritize blockchain fetching over config
        btc_balance = None
        
        # First, try to fetch from blockchain (address or xpub)
        if "btc_address" in wallet_config and wallet_config["btc_address"]:
            print("  Fetching Bitcoin balance from address...")
            btc_balance = self.fetch_bitcoin_balance(
                address=wallet_config["btc_address"],
                xpub=wallet_config.get("btc_xpub")
            )
        elif "btc_xpub" in wallet_config and wallet_config["btc_xpub"]:
            print("  Fetching Bitcoin balance from xpub...")
            btc_balance = self.fetch_bitcoin_balance(xpub=wallet_config["btc_xpub"])
        
        # If blockchain fetch succeeded, use it (even if 0)
        if btc_balance is not None:
            balances["BTC"] = btc_balance
            if btc_balance > 0:
                print(f"    BTC: {btc_balance:.8f} (from blockchain)")
            else:
                print(f"    BTC: {btc_balance:.8f} (from blockchain - no balance)")
        # Fallback to config only if blockchain fetch failed
        elif "btc_balance" in wallet_config and wallet_config["btc_balance"] is not None:
            try:
                btc_balance = float(wallet_config["btc_balance"])
                if btc_balance > 0:
                    balances["BTC"] = btc_balance
                    print(f"    BTC: {btc_balance:.8f} (from config - blockchain fetch failed)")
            except (ValueError, TypeError):
                print("    Invalid btc_balance in config")
        
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
                
                # Debug: Check API response structure
                print(f"    Debug: BlockCypher API status: {response.status_code}")
                print(f"    Debug: Response keys: {list(data.keys())}")
                
                if "txs" not in data:
                    print(f"    Warning: No 'txs' key in BlockCypher response")
                    print(f"    Available keys: {list(data.keys())}")
                    if "error" in data:
                        print(f"    Error message: {data.get('error')}")
                    return []
                
                txs = data.get("txs", [])
                print(f"    Debug: Found {len(txs)} transactions in API response")
                
                if len(txs) > 0:
                    print(f"    Debug: First transaction keys: {list(txs[0].keys())}")
                    print(f"    Debug: First transaction hash: {txs[0].get('hash', 'N/A')}")
                
                # Process transactions
                for tx in txs:
                    tx_hash = tx.get("hash", "")
                    tx_time = tx.get("confirmed", "")
                    
                    # Parse timestamp
                    timestamp = None
                    if tx_time:
                        try:
                            from datetime import datetime
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
                if 'response' in locals():
                    print(f"    Response status code: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"    Error response: {error_data}")
                    except:
                        print(f"    Error response text: {response.text[:500]}")
                return []
            except Exception as e:
                print(f"    Unexpected error fetching Bitcoin transactions: {e}")
                import traceback
                traceback.print_exc()
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
                # Get normal transactions using Etherscan API V2
                # V2 requires chainid parameter (1 = Ethereum Mainnet)
                url = "https://api.etherscan.io/v2/api"
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": limit,
                    "sort": "asc",  # Oldest first
                    "chainid": "1",  # Ethereum Mainnet (required for V2)
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
                
                # Debug: Check Etherscan API response
                print(f"    Debug: Etherscan API status: {response.status_code}")
                print(f"    Debug: Etherscan response status field: {data.get('status')}")
                print(f"    Debug: Etherscan response message: {data.get('message', 'N/A')}")
                
                if data.get("status") != "1":
                    error_msg = data.get("message", "Unknown error")
                    result = data.get("result", "")
                    print(f"    Etherscan API error: {error_msg}")
                    if "Invalid API Key" in str(error_msg):
                        print("    Your Etherscan API key may be invalid. Check your config.")
                    elif "rate limit" in str(error_msg).lower() or "Max rate limit" in str(error_msg):
                        print("    Rate limit exceeded. Please wait and try again later.")
                    elif "No transactions found" in str(result) or result == "[]":
                        print("    No transactions found for this address (this is normal if the address has no activity)")
                    else:
                        print(f"    Result: {result[:200] if result else 'N/A'}")
                    return []
                
                result = data.get("result", [])
                if isinstance(result, str):
                    # Sometimes Etherscan returns error messages as strings in result
                    if "rate limit" in result.lower() or "max rate limit" in result.lower():
                        print(f"    Rate limit error in result: {result}")
                        return []
                    result = []
                
                print(f"    Debug: Found {len(result)} transactions in Etherscan response")
                
                if len(result) > 0 and isinstance(result, list):
                    print(f"    Debug: First transaction keys: {list(result[0].keys()) if isinstance(result[0], dict) else 'N/A'}")
                
                # Process transactions (status is already checked above)
                if isinstance(result, list) and len(result) > 0:
                    for tx in result:
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
                                from datetime import datetime
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
                
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"    Error fetching transactions: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                print(f"    Error fetching Ethereum transaction history: {e}")
                if 'response' in locals():
                    print(f"    Response status code: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"    Error response: {error_data}")
                    except:
                        print(f"    Error response text: {response.text[:500]}")
                return []
            except Exception as e:
                print(f"    Unexpected error fetching Ethereum transactions: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        return transactions

