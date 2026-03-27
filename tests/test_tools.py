"""
Python計算ツールのユニットテスト
設計書の方針: 正常系・境界値（ゼロ除算）・異常系をテスト
"""
import pytest
from src.tools.financial_calc import FinancialCalcTool, TrendAnalysisTool
from src.tools.valuation_calc import ValuationCalcTool


class TestFinancialCalcTool:
    """FinancialCalcTool: ROA/ROE/EPS等の財務指標計算"""

    def setup_method(self):
        self.tool = FinancialCalcTool()

    def _run(self, **kwargs):
        return self.tool._run(**kwargs)

    # 正常系
    def test_normal_case(self):
        result = self._run(
            net_income=100_000_000,
            total_assets=1_000_000_000,
            equity=500_000_000,
            shares_outstanding=1_000_000,
            revenue=800_000_000,
            operating_income=80_000_000,
            current_assets=300_000_000,
            current_liabilities=150_000_000,
            interest_bearing_debt=200_000_000,
            inventory=50_000_000,
            receivables=100_000_000,
            payables=80_000_000,
            cogs=500_000_000,
        )
        assert result["ROA"] == pytest.approx(0.1, rel=1e-3)
        assert result["ROE"] == pytest.approx(0.2, rel=1e-3)
        assert result["EPS"] == pytest.approx(100.0, rel=1e-3)
        assert result["operating_margin"] == pytest.approx(0.1, rel=1e-3)
        assert result["equity_ratio"] == pytest.approx(0.5, rel=1e-3)
        assert result["current_ratio"] == pytest.approx(2.0, rel=1e-3)
        assert result["de_ratio"] == pytest.approx(0.4, rel=1e-3)
        assert result["asset_turnover"] == pytest.approx(0.8, rel=1e-3)
        assert "ccc_days" in result

    # 境界値: ゼロ除算が発生しないこと
    def test_zero_divisors(self):
        result = self._run(
            net_income=100_000_000,
            total_assets=0,       # ゼロ（分母）
            equity=0,             # ゼロ（分母）
            shares_outstanding=0, # ゼロ（分母）
            revenue=0,            # ゼロ（分母）
            operating_income=80_000_000,
            current_assets=300_000_000,
            current_liabilities=0,
            interest_bearing_debt=200_000_000,
            inventory=50_000_000,
            receivables=100_000_000,
            payables=80_000_000,
            cogs=0,               # ゼロ（分母）
        )
        # ゼロ除算で None になること（クラッシュしないこと）
        assert result["ROA"] is None
        assert result["ROE"] is None
        assert result["EPS"] is None
        assert result["asset_turnover"] is None


class TestTrendAnalysisTool:
    """TrendAnalysisTool: CAGR/トレンド方向/直近変化率計算"""

    def setup_method(self):
        self.tool = TrendAnalysisTool()

    def _run(self, values, years):
        return self.tool._run(values=values, years=years)

    def test_growth_trend(self):
        values = [100, 110, 121, 133, 146]
        years = [2020, 2021, 2022, 2023, 2024]
        result = self._run(values, years)
        assert result["trend"] == "改善"
        assert result["cagr"] == pytest.approx(0.10, rel=1e-2)
        assert result["data_points"] == 5

    def test_decline_trend(self):
        values = [200, 180, 160, 140]
        years = [2021, 2022, 2023, 2024]
        result = self._run(values, years)
        assert result["trend"] == "悪化"

    def test_insufficient_data(self):
        result = self._run([100], [2024])
        assert "error" in result


class TestValuationCalcTool:
    """ValuationCalcTool: DCF法・マルチプル法の企業価値計算"""

    def setup_method(self):
        self.tool = ValuationCalcTool()

    def test_dcf_normal(self):
        result = self.tool._run(
            action="dcf",
            free_cash_flows=[50_000_000, 55_000_000, 60_000_000],
            revenue_cagr=0.05,
            operating_margin=0.10,
            tax_rate=0.30,
            capex_ratio=0.05,
            risk_free_rate=0.01,
            equity_risk_premium=0.055,
            beta=1.0,
            debt_cost=0.02,
            debt_ratio=0.3,
            terminal_growth_rate=0.02,
            projection_years=5,
            shares_outstanding=1_000_000,
            net_debt=100_000_000,
        )
        assert "wacc" in result
        assert "intrinsic_price_per_share" in result
        assert result["wacc"] > 0

    def test_multiples_normal(self):
        result = self.tool._run(
            action="multiples",
            target_eps=100.0,
            target_ebitda=100_000_000,
            target_net_debt=50_000_000,
            peer_pers=[15.0, 18.0, 12.0],
            peer_ev_ebitdas=[8.0, 10.0, 7.0],
            shares_outstanding=1_000_000,
        )
        assert result["median_peer_per"] == pytest.approx(15.0)
        assert result["per_implied_price"] == pytest.approx(1500.0)
        assert "ev_ebitda_implied_price" in result

    def test_unknown_action(self):
        result = self.tool._run(action="unknown")
        assert "error" in result
