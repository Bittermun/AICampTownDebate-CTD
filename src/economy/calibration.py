"""Economy calibration helpers based on runway and EV constraints."""
from dataclasses import dataclass, asdict
from math import ceil


@dataclass
class CalibrationInputs:
    target_survival_rounds: int
    avg_generation_cost: float
    avg_bet_size: float
    avg_fee_rate: float = 0.15
    edge_win_rate: float = 0.60
    reserve_rounds: float = 1.0


@dataclass
class CalibrationResult:
    initial_balance: int
    max_debt: int
    tokens_per_round: int
    betting_fee_start: float
    betting_fee_cap: float
    loss_per_round_estimate: float
    fee_positive_ev_upper_bound: float
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def derive_economy_params(inputs: CalibrationInputs) -> CalibrationResult:
    if inputs.target_survival_rounds < 1:
        raise ValueError("target_survival_rounds must be >= 1")
    if not (0.0 <= inputs.avg_fee_rate <= 1.0):
        raise ValueError("avg_fee_rate must be between 0 and 1")
    if not (0.5 < inputs.edge_win_rate < 1.0):
        raise ValueError("edge_win_rate must be between 0.5 and 1.0")

    # Estimated burn for a losing round: generation + losing stake + paid fee.
    loss_per_round = inputs.avg_generation_cost + inputs.avg_bet_size * (1.0 + inputs.avg_fee_rate)

    required_rounds = inputs.target_survival_rounds + max(0.0, inputs.reserve_rounds)
    initial_balance = ceil(loss_per_round * required_rounds)

    # Let debt provide partial extra runway without dominating behavior.
    max_debt = ceil(initial_balance * 0.25)

    # Keep round reward below full loss to preserve pressure while allowing recovery.
    tokens_per_round = ceil(loss_per_round * 0.75)

    # EV for even-odds stake model: EV/stake = 2p - 1 - fee
    fee_positive_ev_upper_bound = max(0.0, (2 * inputs.edge_win_rate - 1.0) - 0.02)

    betting_fee_start = min(0.05, fee_positive_ev_upper_bound / 2 if fee_positive_ev_upper_bound > 0 else 0.01)
    betting_fee_cap = min(0.50, max(betting_fee_start, fee_positive_ev_upper_bound))

    notes = [
        f"Estimated losing-round burn: {loss_per_round:.2f} tokens",
        "initial_balance derived from target survival runway plus reserve",
        "tokens_per_round set to 75% of losing-round burn to maintain pressure",
        f"fee upper bound for {inputs.edge_win_rate:.0%} edge-positive EV: {fee_positive_ev_upper_bound:.3f}",
    ]

    return CalibrationResult(
        initial_balance=initial_balance,
        max_debt=max_debt,
        tokens_per_round=tokens_per_round,
        betting_fee_start=round(betting_fee_start, 3),
        betting_fee_cap=round(betting_fee_cap, 3),
        loss_per_round_estimate=round(loss_per_round, 3),
        fee_positive_ev_upper_bound=round(fee_positive_ev_upper_bound, 3),
        notes=notes,
    )
