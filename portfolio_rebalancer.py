"""
Portfolio Rebalancing Calculator
Calculates exact buy/sell amounts needed to reach target allocations
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from portfolio_evaluator import Asset

try:
    from constants import DEFAULT_TARGET_ALLOCATIONS, COIN_NAMES, REBALANCE_THRESHOLD
except ImportError:
    # Fallback if constants module not available
    DEFAULT_TARGET_ALLOCATIONS = {
        "BTC": 50.0,
        "ETH": 20.0,
        "XRP": 15.0,
        "SOL": 10.0,
        "LINK": 5.0
    }
    COIN_NAMES = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "XRP": "Ripple",
        "SOL": "Solana",
        "LINK": "Chainlink"
    }
    REBALANCE_THRESHOLD = 2.0


@dataclass
class RebalancingAction:
    """Represents a single rebalancing action for an asset"""
    symbol: str
    name: str
    current_allocation: float  # Current allocation percentage
    target_allocation: float   # Target allocation percentage
    allocation_diff: float     # Difference (target - current)
    current_value: float       # Current value in portfolio
    target_value: float        # Target value needed
    value_diff: float          # Amount to buy (positive) or sell (negative)
    current_amount: float      # Current amount of asset
    target_amount: float       # Target amount needed
    amount_diff: float         # Amount to buy (positive) or sell (negative)
    action: str                # "BUY", "SELL", or "HOLD"
    current_price: float       # Current price per unit


class PortfolioRebalancer:
    """Calculates rebalancing actions to reach target allocations"""
    
    def __init__(self, target_allocations: Optional[Dict[str, float]] = None):
        """
        Initialize rebalancer with target allocations
        
        Args:
            target_allocations: Dictionary mapping asset symbols to target percentages.
                              If None, uses DEFAULT_TARGET_ALLOCATIONS.
                              Values should sum to 100.
        """
        if target_allocations is None:
            self.target_allocations = DEFAULT_TARGET_ALLOCATIONS.copy()
        else:
            self.target_allocations = target_allocations.copy()
        
        # Validate that allocations sum to 100 (with small tolerance for floating point)
        total = sum(self.target_allocations.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Target allocations must sum to 100%, but sum to {total:.2f}%. "
                f"Please adjust your target allocations."
            )
    
    def calculate_rebalancing(
        self, 
        portfolio: Dict[str, Asset],
        rebalance_threshold: float = REBALANCE_THRESHOLD,
        market_data: Optional[Dict] = None
    ) -> List[RebalancingAction]:
        """
        Calculate rebalancing actions needed to reach target allocations
        
        Args:
            portfolio: Dictionary mapping asset symbols to Asset objects
            rebalance_threshold: Minimum allocation difference (%) to trigger rebalancing
            market_data: Optional market data dictionary with prices for assets not in portfolio
            
        Returns:
            List of RebalancingAction objects, sorted by absolute allocation difference
        """
        # Calculate total portfolio value
        total_value = sum(asset.value for asset in portfolio.values())
        
        if total_value == 0:
            return []
        
        actions = []
        
        # Process each asset in target allocations
        for symbol, target_pct in self.target_allocations.items():
            if symbol in portfolio:
                asset = portfolio[symbol]
                current_pct = asset.allocation_percent
                allocation_diff = target_pct - current_pct
                
                # Calculate target value and difference
                target_value = (target_pct / 100.0) * total_value
                value_diff = target_value - asset.value
                
                # Calculate target amount and difference
                if asset.current_price > 0:
                    target_amount = target_value / asset.current_price
                    amount_diff = target_amount - asset.amount
                else:
                    target_amount = asset.amount
                    amount_diff = 0.0
                
                # Determine action
                if abs(allocation_diff) < rebalance_threshold:
                    action = "HOLD"
                elif value_diff > 0:
                    action = "BUY"
                elif value_diff < 0:
                    action = "SELL"
                else:
                    action = "HOLD"
                
                actions.append(RebalancingAction(
                    symbol=symbol,
                    name=asset.name,
                    current_allocation=current_pct,
                    target_allocation=target_pct,
                    allocation_diff=allocation_diff,
                    current_value=asset.value,
                    target_value=target_value,
                    value_diff=value_diff,
                    current_amount=asset.amount,
                    target_amount=target_amount,
                    amount_diff=amount_diff,
                    action=action,
                    current_price=asset.current_price
                ))
            else:
                # Asset in target but not in portfolio - need to buy
                target_value = (target_pct / 100.0) * total_value
                
                # Try to get price from market data if available
                price = 0.0
                name = symbol
                if market_data and symbol in market_data:
                    price = market_data[symbol].get("current_price", 0.0)
                    # Try to get name from coin names mapping
                    name = COIN_NAMES.get(symbol, symbol)
                
                # Calculate target amount if we have price
                if price > 0:
                    target_amount = target_value / price
                    amount_diff = target_amount
                else:
                    target_amount = 0.0
                    amount_diff = 0.0
                
                actions.append(RebalancingAction(
                    symbol=symbol,
                    name=name,
                    current_allocation=0.0,
                    target_allocation=target_pct,
                    allocation_diff=target_pct,
                    current_value=0.0,
                    target_value=target_value,
                    value_diff=target_value,
                    current_amount=0.0,
                    target_amount=target_amount,
                    amount_diff=amount_diff,
                    action="BUY",
                    current_price=price
                ))
        
        # Sort by absolute allocation difference (largest deviations first)
        actions.sort(key=lambda x: abs(x.allocation_diff), reverse=True)
        
        return actions
    
    def print_rebalancing_report(
        self, 
        actions: List[RebalancingAction],
        portfolio_value: float,
        show_hold: bool = False
    ):
        """
        Print a formatted rebalancing report
        
        Args:
            actions: List of RebalancingAction objects
            portfolio_value: Total portfolio value
            show_hold: Whether to show assets that should be held (no action)
        """
        print("=" * 100)
        print("PORTFOLIO REBALANCING REPORT")
        print("=" * 100)
        print(f"Total Portfolio Value: AU${portfolio_value:,.2f}")
        print()
        
        # Separate actions by type
        buy_actions = [a for a in actions if a.action == "BUY"]
        sell_actions = [a for a in actions if a.action == "SELL"]
        hold_actions = [a for a in actions if a.action == "HOLD"]
        
        # Print sell actions first
        if sell_actions:
            print("[SELL] ASSETS TO REDUCE")
            print("-" * 100)
            print(f"{'Asset':<15} {'Current %':<12} {'Target %':<12} {'Diff %':<12} {'Current Value':<18} {'Sell Value':<18} {'Sell Amount':<18}")
            print("-" * 100)
            
            total_sell_value = 0.0
            for action in sell_actions:
                sell_value = abs(action.value_diff)
                total_sell_value += sell_value
                
                sell_amount_str = f"{abs(action.amount_diff):.8f} {action.symbol}" if action.current_price > 0 else "N/A"
                
                print(
                    f"{action.name:<15} "
                    f"{action.current_allocation:>10.2f}% "
                    f"{action.target_allocation:>10.2f}% "
                    f"{action.allocation_diff:>+10.2f}% "
                    f"AU${action.current_value:>15,.2f} "
                    f"AU${sell_value:>15,.2f} "
                    f"{sell_amount_str:>18}"
                )
            
            print("-" * 100)
            print(f"{'TOTAL TO SELL':<51} AU${total_sell_value:>15,.2f}")
            print()
        
        # Print buy actions
        if buy_actions:
            print("[BUY] ASSETS TO INCREASE")
            print("-" * 100)
            print(f"{'Asset':<15} {'Current %':<12} {'Target %':<12} {'Diff %':<12} {'Current Value':<18} {'Buy Value':<18} {'Buy Amount':<18}")
            print("-" * 100)
            
            total_buy_value = 0.0
            for action in buy_actions:
                buy_value = action.value_diff
                total_buy_value += buy_value
                
                if action.current_price > 0:
                    buy_amount_str = f"{action.amount_diff:.8f} {action.symbol}"
                else:
                    buy_amount_str = "Price unknown"
                
                current_value_str = f"AU${action.current_value:>15,.2f}" if action.current_value > 0 else "N/A"
                
                print(
                    f"{action.name:<15} "
                    f"{action.current_allocation:>10.2f}% "
                    f"{action.target_allocation:>10.2f}% "
                    f"{action.allocation_diff:>+10.2f}% "
                    f"{current_value_str:>18} "
                    f"AU${buy_value:>15,.2f} "
                    f"{buy_amount_str:>18}"
                )
            
            print("-" * 100)
            print(f"{'TOTAL TO BUY':<51} AU${total_buy_value:>15,.2f}")
            print()
        
        # Print hold actions if requested
        if show_hold and hold_actions:
            print("[HOLD] ASSETS WITHIN TARGET RANGE")
            print("-" * 100)
            print(f"{'Asset':<15} {'Current %':<12} {'Target %':<12} {'Diff %':<12}")
            print("-" * 100)
            
            for action in hold_actions:
                print(
                    f"{action.name:<15} "
                    f"{action.current_allocation:>10.2f}% "
                    f"{action.target_allocation:>10.2f}% "
                    f"{action.allocation_diff:>+10.2f}%"
                )
            print()
        
        # Summary
        print("=" * 100)
        print("REBALANCING SUMMARY")
        print("=" * 100)
        print(f"Assets to Sell: {len(sell_actions)}")
        print(f"Assets to Buy: {len(buy_actions)}")
        print(f"Assets to Hold: {len(hold_actions)}")
        
        if sell_actions:
            total_sell = sum(abs(a.value_diff) for a in sell_actions)
            print(f"\nTotal Value to Sell: AU${total_sell:,.2f}")
        
        if buy_actions:
            total_buy = sum(a.value_diff for a in buy_actions)
            print(f"Total Value to Buy: AU${total_buy:,.2f}")
            print(f"\nNote: You can use proceeds from sales to fund purchases.")
            print(f"      Net cash needed: AU${max(0, total_buy - (sum(abs(a.value_diff) for a in sell_actions) if sell_actions else 0)):,.2f}")
        
        print()
        print("[!] DISCLAIMER: Rebalancing recommendations are based on target allocations only.")
        print("   Consider transaction fees, tax implications, and market conditions before executing trades.")
        print("=" * 100)
    
    def calculate_deposit_allocation(
        self,
        portfolio: Dict[str, Asset],
        deposit_amount: float,
        market_data: Optional[Dict] = None,
        dca_priorities: Optional[Dict[str, int]] = None
    ) -> Dict[str, Dict]:
        """
        Calculate how to allocate a deposit to under-allocated assets
        
        Args:
            portfolio: Dictionary mapping asset symbols to Asset objects
            deposit_amount: Amount available for deposit
            market_data: Optional market data dictionary with prices
            dca_priorities: Optional dictionary mapping symbols to DCA priorities (0-10)
                          If provided, allocation will be weighted by priority
            
        Returns:
            Dictionary mapping asset symbols to allocation details
        """
        current_total = sum(asset.value for asset in portfolio.values())
        new_total = current_total + deposit_amount
        
        # Get buy actions (under-allocated assets)
        actions = self.calculate_rebalancing(portfolio, market_data=market_data)
        buy_actions = [a for a in actions if a.action == "BUY" and a.value_diff > 0]
        
        if not buy_actions:
            return {}
        
        # Calculate total needed for all under-allocated assets
        total_needed = sum(a.value_diff for a in buy_actions)
        
        # If deposit is less than total needed, allocate proportionally
        # If deposit is more than total needed, allocate based on target allocations
        allocations = {}
        
        if deposit_amount <= total_needed:
            # Calculate weights if priorities provided
            weights = {}
            total_weight = 0.0
            if dca_priorities:
                for action in buy_actions:
                    priority = dca_priorities.get(action.symbol, 5)  # Default priority 5 if not found
                    # Weight = allocation need × (priority + 1) to ensure positive weights
                    # Using (priority + 1) so priority 0 still gets some allocation
                    weight = action.value_diff * (priority + 1)
                    weights[action.symbol] = weight
                    total_weight += weight
            
            # Allocate to each asset
            for action in buy_actions:
                if dca_priorities and total_weight > 0:
                    # Priority-weighted allocation
                    weight = weights.get(action.symbol, 0)
                    proportion = weight / total_weight
                else:
                    # Proportional allocation based on allocation needs (original logic)
                    proportion = action.value_diff / total_needed
                
                allocated = deposit_amount * proportion
                
                # Calculate new values and allocations
                new_value = action.current_value + allocated
                new_allocation = (new_value / new_total) * 100
                
                # Calculate amount to buy
                amount_to_buy = allocated / action.current_price if action.current_price > 0 else 0
                
                allocations[action.symbol] = {
                    "name": action.name,
                    "current_value": action.current_value,
                    "current_allocation": action.current_allocation,
                    "target_allocation": action.target_allocation,
                    "deposit_allocation": allocated,
                    "new_value": new_value,
                    "new_allocation": new_allocation,
                    "amount_to_buy": amount_to_buy,
                    "price": action.current_price
                }
        else:
            # Deposit exceeds total needed - allocate to reach targets, then proportionally
            remaining_deposit = deposit_amount
            
            # First, allocate to reach exact targets
            for action in buy_actions:
                needed = action.value_diff
                allocated = min(needed, remaining_deposit)
                remaining_deposit -= allocated
                
                new_value = action.current_value + allocated
                new_allocation = (new_value / new_total) * 100
                amount_to_buy = allocated / action.current_price if action.current_price > 0 else 0
                
                allocations[action.symbol] = {
                    "name": action.name,
                    "current_value": action.current_value,
                    "current_allocation": action.current_allocation,
                    "target_allocation": action.target_allocation,
                    "deposit_allocation": allocated,
                    "new_value": new_value,
                    "new_allocation": new_allocation,
                    "amount_to_buy": amount_to_buy,
                    "price": action.current_price
                }
            
            # If there's remaining deposit, allocate proportionally based on target allocations
            if remaining_deposit > 0:
                total_target_pct = sum(a.target_allocation for a in buy_actions)
                for action in buy_actions:
                    proportion = action.target_allocation / total_target_pct
                    additional = remaining_deposit * proportion
                    
                    allocations[action.symbol]["deposit_allocation"] += additional
                    allocations[action.symbol]["new_value"] += additional
                    allocations[action.symbol]["new_allocation"] = (
                        allocations[action.symbol]["new_value"] / new_total
                    ) * 100
                    allocations[action.symbol]["amount_to_buy"] += (
                        additional / action.current_price if action.current_price > 0 else 0
                    )
        
        return allocations
    
    def print_deposit_allocation_report(
        self,
        portfolio: Dict[str, Asset],
        deposit_amount: float,
        market_data: Optional[Dict] = None,
        dca_priorities: Optional[Dict[str, int]] = None
    ):
        """
        Print a formatted report showing how to allocate a deposit
        
        Args:
            portfolio: Dictionary mapping asset symbols to Asset objects
            deposit_amount: Amount available for deposit
            market_data: Optional market data dictionary with prices
        """
        current_total = sum(asset.value for asset in portfolio.values())
        allocations = self.calculate_deposit_allocation(portfolio, deposit_amount, market_data, dca_priorities)
        
        if not allocations:
            print("\n" + "=" * 100)
            print("DEPOSIT ALLOCATION REPORT")
            print("=" * 100)
            print("No under-allocated assets found. Portfolio is already balanced or over-allocated.")
            print("=" * 100)
            return
        
        new_total = current_total + deposit_amount
        
        print("\n" + "=" * 100)
        print("DEPOSIT ALLOCATION REPORT")
        print("=" * 100)
        print(f"Current Portfolio Value: AU${current_total:,.2f}")
        print(f"Deposit Amount: AU${deposit_amount:,.2f}")
        print(f"New Portfolio Value: AU${new_total:,.2f}")
        print()
        print("ALLOCATION PLAN")
        print("-" * 100)
        print(f"{'Asset':<15} {'Current %':<12} {'Target %':<12} {'Deposit':<18} {'New %':<12} {'Buy Amount':<18}")
        print("-" * 100)
        
        total_allocated = 0.0
        for symbol, details in sorted(allocations.items(), key=lambda x: x[1]["deposit_allocation"], reverse=True):
            total_allocated += details["deposit_allocation"]
            buy_amount_str = f"{details['amount_to_buy']:.8f} {symbol}" if details['price'] > 0 else "N/A"
            
            print(
                f"{details['name']:<15} "
                f"{details['current_allocation']:>10.2f}% "
                f"{details['target_allocation']:>10.2f}% "
                f"AU${details['deposit_allocation']:>15,.2f} "
                f"{details['new_allocation']:>10.2f}% "
                f"{buy_amount_str:>18}"
            )
        
        print("-" * 100)
        print(f"{'TOTAL ALLOCATED':<51} AU${total_allocated:>15,.2f}")
        if total_allocated < deposit_amount:
            remaining = deposit_amount - total_allocated
            print(f"{'REMAINING (unallocated)':<51} AU${remaining:>15,.2f}")
        print()
        
        # Show what allocations will be after deposit
        print("PROJECTED ALLOCATIONS AFTER DEPOSIT")
        print("-" * 100)
        print(f"{'Asset':<15} {'Current %':<12} {'After Deposit %':<18} {'Target %':<12} {'Status':<15}")
        print("-" * 100)
        
        # Get all assets (including those not getting deposits)
        all_assets = {}
        for symbol, asset in portfolio.items():
            if symbol in allocations:
                all_assets[symbol] = {
                    "name": asset.name,
                    "current": asset.allocation_percent,
                    "after": allocations[symbol]["new_allocation"],
                    "target": self.target_allocations.get(symbol, 0.0)
                }
            else:
                # Asset not getting deposit - calculate new allocation
                new_allocation = (asset.value / new_total) * 100
                all_assets[symbol] = {
                    "name": asset.name,
                    "current": asset.allocation_percent,
                    "after": new_allocation,
                    "target": self.target_allocations.get(symbol, 0.0)
                }
        
        # Add assets in target but not in portfolio
        for symbol, target_pct in self.target_allocations.items():
            if symbol not in all_assets:
                if symbol in allocations:
                    all_assets[symbol] = {
                        "name": allocations[symbol]["name"],
                        "current": 0.0,
                        "after": allocations[symbol]["new_allocation"],
                        "target": target_pct
                    }
        
        for symbol, details in sorted(all_assets.items(), key=lambda x: x[1]["after"], reverse=True):
            diff = details["after"] - details["target"]
            if abs(diff) < 2.0:
                status = "✓ On Target"
            elif diff > 0:
                status = "Over Target"
            else:
                status = "Under Target"
            
            print(
                f"{details['name']:<15} "
                f"{details['current']:>10.2f}% "
                f"{details['after']:>16.2f}% "
                f"{details['target']:>10.2f}% "
                f"{status:>15}"
            )
        
        print()
        print("=" * 100)
        print("NOTE: This allocation strategy avoids selling assets and capital gains taxes.")
        print("      If deposit is insufficient to reach targets, consider a hybrid approach")
        print("      (partial deposit + selling over-allocated assets).")
        print("=" * 100)
    
    def get_rebalancing_summary(self, actions: List[RebalancingAction]) -> Dict:
        """
        Get a summary dictionary of rebalancing actions
        
        Args:
            actions: List of RebalancingAction objects
            
        Returns:
            Dictionary with summary statistics
        """
        buy_actions = [a for a in actions if a.action == "BUY"]
        sell_actions = [a for a in actions if a.action == "SELL"]
        hold_actions = [a for a in actions if a.action == "HOLD"]
        
        total_buy_value = sum(a.value_diff for a in buy_actions)
        total_sell_value = sum(abs(a.value_diff) for a in sell_actions)
        
        return {
            "total_actions": len(actions),
            "buy_count": len(buy_actions),
            "sell_count": len(sell_actions),
            "hold_count": len(hold_actions),
            "total_buy_value": total_buy_value,
            "total_sell_value": total_sell_value,
            "net_cash_needed": max(0, total_buy_value - total_sell_value),
            "actions": actions
        }

