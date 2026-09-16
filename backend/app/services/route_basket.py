"""Canonical domestic route basket for the airfare index.

Route weights are proportional to approximate all-India domestic trunk-route
passenger-traffic share (admin-overridable via the routes table / API). The
basket covers the city pairs tracked by the MoSPI CPI airfare component
(07.3.3.1) and the real-time Google Flights collection (gds_adapter).

This module is the single source of truth shared by the seed/bootstrap
scripts and the offline schema tests.

Format: ``{route_key: (weight, distance_tier)}``.
"""

ROUTE_BASKET = {
    # route: (weight, distance_tier)
    "DEL-BOM": (0.14, "trunk"),
    "DEL-BLR": (0.11, "trunk"),
    "BOM-BLR": (0.09, "trunk"),
    "DEL-MAA": (0.08, "trunk"),
    "DEL-CCU": (0.07, "trunk"),
    "BOM-MAA": (0.06, "trunk"),
    "BLR-HYD": (0.06, "regional"),
    "DEL-HYD": (0.07, "trunk"),
    "BOM-CCU": (0.05, "trunk"),
    "DEL-PNQ": (0.05, "regional"),
    "DEL-GOI": (0.05, "regional"),
    "BLR-MAA": (0.04, "regional"),
    "DEL-COK": (0.04, "regional"),
    "BOM-GOI": (0.03, "regional"),
    "CCU-BLR": (0.03, "regional"),
    "DEL-ATQ": (0.03, "regional"),
}