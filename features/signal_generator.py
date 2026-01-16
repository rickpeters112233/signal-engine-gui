"""
Trading Signal Generator
Implements the complete BUY/SELL/HOLD signal logic based on backtested rules.
"""

from typing import Tuple


class TradingSignalGenerator:
    """
    Generates trading signals based on phi_sigma and directional_indicator features.
    Maintains position state for stop-loss and take-profit logic.
    """

    # Entry thresholds (18x edge)
    PHI_SIGMAT_ENTRY = 4.0
    DIRECTIONAL_ENTRY = 0.5

    # Exit thresholds
    STOP_LOSS_PCT = 0.0010   # 0.10% Stop-Loss
    TAKE_PROFIT_PCT = 0.0005  # 0.05% Take-Profit

    def __init__(self):
        """Initialize the signal generator with no open position."""
        self.entry_price = 0.0
        self.position_open = False

    def generate_signal(
        self,
        phi_sigma_value: float,
        directional_indicator_value: float,
        current_price: float
    ) -> Tuple[str, dict]:
        """
        Generates a complete BUY/HOLD/SELL signal based on the backtested rules.

        Args:
            phi_sigma_value: Latest phi_sigma feature value.
            directional_indicator_value: Latest directional_indicator feature value.
            current_price: The current minute's closing price.

        Returns:
            Tuple of (signal, metadata):
                signal: 'BUY', 'SELL_PROFIT', 'SELL_STOP', or 'HOLD'
                metadata: Dict with additional info (entry_price, pnl_pct, etc.)
        """
        metadata = {
            'entry_price': self.entry_price,
            'position_open': self.position_open,
            'current_price': current_price,
            'pnl_pct': 0.0,
            'stop_loss_price': 0.0,
            'take_profit_price': 0.0,
        }

        # 1. CHECK FOR OPEN POSITION (Exit Rules)
        if self.entry_price > 0 and self.position_open:
            stop_loss_limit = self.entry_price * (1 - self.STOP_LOSS_PCT)
            take_profit_limit = self.entry_price * (1 + self.TAKE_PROFIT_PCT)

            metadata['stop_loss_price'] = stop_loss_limit
            metadata['take_profit_price'] = take_profit_limit
            metadata['pnl_pct'] = ((current_price - self.entry_price) / self.entry_price) * 100

            if current_price <= stop_loss_limit:
                # Stop-loss triggered
                self._close_position()
                return 'SELL_STOP', metadata
            elif current_price >= take_profit_limit:
                # Take-profit triggered
                self._close_position()
                return 'SELL_PROFIT', metadata
            else:
                # Position open but no exit trigger
                return 'HOLD', metadata

        # 2. CHECK FOR BUY ENTRY (Entry Rule)
        if (phi_sigma_value >= self.PHI_SIGMAT_ENTRY) and \
           (directional_indicator_value >= self.DIRECTIONAL_ENTRY):
            self._open_position(current_price)
            metadata['entry_price'] = self.entry_price
            metadata['position_open'] = True
            return 'BUY', metadata

        # 3. NO ACTION
        return 'HOLD', metadata

    def _open_position(self, price: float):
        """Open a new position at the given price."""
        self.entry_price = price
        self.position_open = True

    def _close_position(self):
        """Close the current position."""
        self.entry_price = 0.0
        self.position_open = False

    def get_state(self) -> dict:
        """Get current position state."""
        return {
            'entry_price': self.entry_price,
            'position_open': self.position_open,
        }

    def reset(self):
        """Reset to initial state (no position)."""
        self.entry_price = 0.0
        self.position_open = False


# Standalone function for simple usage
def generate_complete_signal(
    phi_sigmat_value: float,
    directional_indicatort_value: float,
    current_price: float,
    entry_price: float
) -> str:
    """
    Generates a complete BUY/HOLD/SELL signal based on the final backtested rules
    for the gold market, which showed an 18x stronger signal than baseline.

    Args:
        phi_sigmat_value (float): Latest phi_sigma frozen feature.
        directional_indicatort_value (float): Latest directional_indicator feature.
        current_price (float): The current minute's price.
        entry_price (float): The price at which the current position was opened (0 if no position).

    Returns:
        str: 'BUY', 'SELL_PROFIT', 'SELL_STOP', or 'HOLD'.
    """
    # --- Actionable BUY Entry Rules (18x Edge) ---
    PHI_SIGMAT_ENTRY = 4.0
    DIRECTIONAL_ENTRY = 0.5

    # --- Actionable SELL Exit Rules (Low-Risk/Profit-Taking) ---
    STOP_LOSS_PCT = 0.0010   # 0.10% Stop-Loss (Low 2.27% Max Drawdown)
    TAKE_PROFIT_PCT = 0.0005  # 0.05% Take-Profit (High Avg Return per Trade)

    # 1. CHECK FOR OPEN POSITION (Exit Rules)
    if entry_price > 0:
        stop_loss_limit = entry_price * (1 - STOP_LOSS_PCT)
        take_profit_limit = entry_price * (1 + TAKE_PROFIT_PCT)

        if current_price <= stop_loss_limit:
            return 'SELL_STOP'
        elif current_price >= take_profit_limit:
            return 'SELL_PROFIT'
        else:
            return 'HOLD'  # Position open, but neither exit trigger hit

    # 2. CHECK FOR BUY ENTRY (Entry Rule)
    elif (phi_sigmat_value >= PHI_SIGMAT_ENTRY) and \
         (directional_indicatort_value >= DIRECTIONAL_ENTRY):
        return 'BUY'

    # 3. NO ACTION
    else:
        return 'HOLD'
