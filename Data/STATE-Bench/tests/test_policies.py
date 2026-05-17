"""Unit tests for the deterministic policy engine."""

from __future__ import annotations

from domains.travel.policies import (
    check_cancellation_policy,
    check_change_policy,
    check_delay_compensation,
    check_loyalty_point_redemption,
    check_upgrade_eligibility,
    get_baggage_allowance,
)


class TestCancellationPolicy:
    def test_airline_cancelled_full_refund(self):
        result = check_cancellation_policy("economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, True, 500)
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_within_24h_free_domestic(self):
        result = check_cancellation_policy("economy", "2026-06-15T08:00:00", "2026-06-15T10:00:00", False, False, 500)
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_within_48h_free_international(self):
        result = check_cancellation_policy(
            "economy", "2026-06-14T08:00:00", "2026-06-15T10:00:00", False, False, 500, route_type="international"
        )
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_outside_48h_international_not_free(self):
        result = check_cancellation_policy(
            "economy", "2026-06-12T08:00:00", "2026-06-15T10:00:00", False, False, 500, route_type="international"
        )
        assert result["eligible"] is True
        assert result["fee"] == max(75, int(500 * 0.20))  # $100

    def test_insurance_covers(self):
        result = check_cancellation_policy("economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", True, False, 500)
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_basic_economy_ineligible(self):
        result = check_cancellation_policy(
            "basic_economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 300
        )
        assert result["eligible"] is False

    def test_economy_domestic_percentage_fee(self):
        result = check_cancellation_policy("economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 500)
        assert result["eligible"] is True
        assert result["fee"] == 75  # 15% of 500 = 75 > 50

    def test_economy_domestic_minimum_50(self):
        result = check_cancellation_policy("economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 200)
        assert result["eligible"] is True
        assert result["fee"] == 50  # 15% of 200 = 30, min $50

    def test_economy_international_higher_fee(self):
        result = check_cancellation_policy(
            "economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 500, route_type="international"
        )
        assert result["eligible"] is True
        assert result["fee"] == 100  # 20% of 500 = 100 > 75

    def test_economy_international_minimum_75(self):
        result = check_cancellation_policy(
            "economy", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 200, route_type="international"
        )
        assert result["eligible"] is True
        assert result["fee"] == 75  # 20% of 200 = 40, min $75

    def test_business_domestic_5_percent(self):
        result = check_cancellation_policy("business", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 800)
        assert result["eligible"] is True
        assert result["fee"] == 40  # 5% of 800

    def test_business_international_8_percent(self):
        result = check_cancellation_policy(
            "business", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 800, route_type="international"
        )
        assert result["eligible"] is True
        assert result["fee"] == 64  # 8% of 800

    def test_first_class_free(self):
        result = check_cancellation_policy("first", "2026-06-10T10:00:00", "2026-06-15T10:00:00", False, False, 1500)
        assert result["eligible"] is True
        assert result["fee"] == 0


class TestChangePolicy:
    def test_within_24h_free_domestic(self):
        result = check_change_policy("economy", "2026-06-15T08:00:00", "2026-06-15T10:00:00", False)
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_within_48h_free_international(self):
        result = check_change_policy(
            "economy", "2026-06-14T08:00:00", "2026-06-15T10:00:00", False, route_type="international"
        )
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_schedule_change_free(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-20",
            change_reason="schedule_change",
        )
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_weather_free(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-20",
            change_reason="weather",
        )
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_basic_economy_blocked(self):
        result = check_change_policy(
            "basic_economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
        )
        assert result["eligible"] is False

    def test_business_free(self):
        result = check_change_policy(
            "business",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
        )
        assert result["eligible"] is True
        assert result["fee"] == 0

    def test_economy_domestic_personal_more_than_7d(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-25",
            change_reason="personal",
        )
        assert result["eligible"] is True
        assert result["fee"] == 75

    def test_economy_domestic_personal_within_7d(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-18",
            change_reason="personal",
        )
        assert result["eligible"] is True
        assert result["fee"] == 150

    def test_economy_international_personal_more_than_7d(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-25",
            change_reason="personal",
            route_type="international",
        )
        assert result["eligible"] is True
        assert result["fee"] == 100

    def test_economy_international_personal_within_7d(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-18",
            change_reason="personal",
            route_type="international",
        )
        assert result["eligible"] is True
        assert result["fee"] == 200

    def test_economy_domestic_medical_half_fee(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-25",
            change_reason="medical",
        )
        assert result["eligible"] is True
        assert result["fee"] == 37  # 75 // 2

    def test_economy_international_medical_half_fee(self):
        result = check_change_policy(
            "economy",
            "2026-06-10T10:00:00",
            "2026-06-15T10:00:00",
            False,
            departure_date="2026-06-25",
            change_reason="medical",
            route_type="international",
        )
        assert result["eligible"] is True
        assert result["fee"] == 50  # 100 // 2


class TestDelayCompensation:
    def test_under_2h_nothing(self):
        result = check_delay_compensation(90)
        assert result["compensation"] == "none"

    def test_2h_meal_voucher(self):
        result = check_delay_compensation(150)
        assert result["compensation"] == "meal_voucher"

    def test_4h_full(self):
        result = check_delay_compensation(270)
        assert result["compensation"] == "full"

    def test_boundary_120(self):
        result = check_delay_compensation(120)
        assert result["compensation"] == "meal_voucher"

    def test_boundary_240(self):
        result = check_delay_compensation(240)
        assert result["compensation"] == "full"


class TestLoyaltyRedemption:
    def test_insufficient_points(self):
        result = check_loyalty_point_redemption("basic", 500, 500)
        assert result["eligible"] is False

    def test_basic_redemption(self):
        result = check_loyalty_point_redemption("basic", 75000, 800)
        assert result["eligible"] is True

    def test_platinum_bonus(self):
        result = check_loyalty_point_redemption("platinum", 100000, 500)
        assert result["eligible"] is True

    def test_full_points_coverage(self):
        # With enough points, remaining cash should be 0 (no cap in V5)
        result = check_loyalty_point_redemption("platinum", 500000, 500)
        assert result["eligible"] is True
        assert result["remaining_cash_payment"] == 0


class TestUpgradeEligibility:
    def test_economy_to_business(self):
        result = check_upgrade_eligibility("economy", "business", "economy", 400)
        assert result["eligible"] is True
        assert result["fare_difference"] == 600  # 2.5 * 400 - 400 = 600

    def test_economy_to_first_blocked(self):
        result = check_upgrade_eligibility("economy", "first", "economy", 400)
        assert result["eligible"] is False

    def test_basic_economy_blocked(self):
        result = check_upgrade_eligibility("economy", "business", "basic_economy", 400)
        assert result["eligible"] is False

    def test_business_to_first(self):
        result = check_upgrade_eligibility("business", "first", "business", 800)
        assert result["eligible"] is True
        assert result["fare_difference"] == 640  # 1.8 * 800 - 800 = 640

    def test_same_cabin(self):
        result = check_upgrade_eligibility("economy", "economy", "economy", 400)
        assert result["eligible"] is False


class TestBaggageAllowance:
    def test_economy_basic_tier(self):
        result = get_baggage_allowance("economy", "basic")
        assert result["checked_bags_free"] == 1
        assert result["checked_bag_fee"] == 35

    def test_basic_economy_no_checked(self):
        result = get_baggage_allowance("basic_economy", "basic")
        assert result["checked_bags_free"] == 0
        assert result["checked_bag_fee"] == 50

    def test_business_platinum(self):
        result = get_baggage_allowance("business", "platinum")
        assert result["checked_bags_free"] == 5  # 2 cabin + 3 platinum

    def test_first_class(self):
        result = get_baggage_allowance("first", "basic")
        assert result["checked_bags_free"] == 3
