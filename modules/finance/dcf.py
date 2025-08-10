
"""Discounted Cash Flow (DCF) simulations (vectorized & jump-diffusion)."""
from __future__ import annotations
from typing import Optional
import numpy as np

def monte_carlo_dcf_simple(
    last_fcf: float,
    forecast_years: int = 5,
    n_sims: int = 10_000,
    wacc_mu: float = 0.15, wacc_sigma: float = 0.03,
    g_mu: float = 0.04,  g_sigma: float = 0.01,
    seed: Optional[int] = 42, 
) -> np.ndarray:
    """Vectorized Monte-Carlo DCF (PV of explicit FCFs + Gordon terminal value).
    Fixes:
      • Guarantees WACC > g and WACC > 0
      • Caps g at −5% and 15%
      • Discounts terminal value N years (not N+1)
      • Returns np.ndarray of intrinsic values (length = n_sims)
    """
    if seed is not None:
        np.random.seed(seed)

    waccs = np.clip(np.random.normal(wacc_mu, wacc_sigma, n_sims), 0.01, None)
    gs    = np.random.normal(g_mu,  g_sigma,  n_sims)

    bad = (gs >= waccs - 0.01) | (gs < -0.05) | (gs > 0.15)
    while bad.any():
        waccs[bad] = np.clip(np.random.normal(wacc_mu, wacc_sigma, bad.sum()), 0.01, None)
        gs[bad]    = np.random.normal(g_mu, g_sigma, bad.sum())
        bad = (gs >= waccs - 0.01) | (gs < -0.05) | (gs > 0.15)

    years         = np.arange(1, forecast_years + 1)
    growth_matrix = (1 + gs[:, None]) ** years
    fcf_matrix    = last_fcf * growth_matrix
    discount      = (1 + waccs[:, None]) ** years
    pv_fcfs       = (fcf_matrix / discount).sum(axis=1)

    fcf_N1 = last_fcf * (1 + gs) ** (forecast_years) * (1 + gs)
    tv     = fcf_N1 / (waccs - gs)
    pv_tv  = tv / (1 + waccs) ** forecast_years

    return pv_fcfs + pv_tv

def monte_carlo_dcf_jump_diffusion(
    last_fcf: float,
    forecast_years: int = 5,
    n_sims: int = 10_000,
    wacc_mu: float = 0.15,
    g_mu: float = 0.04,
    mu: float = 0.10,
    sigma: float = 0.25,
    lambda_: float = 0.1,    # jump intensity
    jump_mu: float = 0.05,   # average jump size
    jump_sigma: float = 0.10 # jump volatility
):
    """Monte-Carlo DCF with jump-diffusion growth for FCF path."""
    results = []
    for _ in range(n_sims):
        fcf = last_fcf
        cashflows = []
        for t in range(1, forecast_years + 1):
            growth = np.random.normal(mu, sigma)
            jump_occurs = np.random.poisson(lambda_)
            jump = float(jump_occurs) * np.random.normal(jump_mu, jump_sigma)
            fcf *= (1 + growth + jump)
            cashflows.append(fcf / ((1 + wacc_mu) ** t))
        terminal = fcf * (1 + g_mu) / (wacc_mu - g_mu)
        cashflows.append(terminal / ((1 + wacc_mu) ** forecast_years))
        results.append(sum(cashflows))
    return np.array(results)
