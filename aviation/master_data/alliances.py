"""Canonical alliance membership — deterministic, source-verified mapping.

Sources:
- Star Alliance: https://www.staralliance.com/en/member-airlines
- Oneworld: https://www.oneworld.com/member-airlines
- SkyTeam: https://www.skyteam.com/en/about/our-members
"""

from __future__ import annotations

ALLIANCES = {
    "Star Alliance": {
        "slug": "star-alliance",
        "founded_year": 1997,
        "headquarters": "Frankfurt, Germany",
    },
    "Oneworld": {
        "slug": "oneworld",
        "founded_year": 1999,
        "headquarters": "New York, USA",
    },
    "SkyTeam": {
        "slug": "skyteam",
        "founded_year": 2000,
        "headquarters": "Amsterdam, Netherlands",
    },
}

ALLIANCE_MEMBERS: dict[str, list[str]] = {
    "Star Alliance": [
        "Aegean Airlines",
        "Air Canada",
        "Air China",
        "Air India",
        "Air New Zealand",
        "ANA All Nippon Airways",
        "Asiana Airlines",
        "Austrian Airlines",
        "Avianca",
        "Brussels Airlines",
        "Copa Airlines",
        "Croatia Airlines",
        "EgyptAir",
        "Ethiopian Airlines",
        "EVA Air",
        "LOT Polish Airlines",
        "Lufthansa",
        "Scandinavian Airlines",
        "Shenzhen Airlines",
        "Singapore Airlines",
        "South African Airways",
        "SWISS",
        "TAP Air Portugal",
        "Thai Airways",
        "Turkish Airlines",
        "United Airlines",
    ],
    "Oneworld": [
        "Alaska Airlines",
        "American Airlines",
        "British Airways",
        "Cathay Pacific",
        "Fiji Airways",
        "Finnair",
        "Iberia",
        "Japan Airlines",
        "Malaysia Airlines",
        "Oman Air",
        "Qantas Airways",
        "Qatar Airways",
        "Royal Air Maroc",
        "Royal Jordanian",
        "SriLankan Airlines",
    ],
    "SkyTeam": [
        "Aerolíneas Argentinas",
        "Aeroméxico",
        "Air Europa",
        "Air France",
        "China Airlines",
        "China Eastern Airlines",
        "Czech Airlines",
        "Delta Air Lines",
        "Garuda Indonesia",
        "ITA Airways",
        "Kenya Airways",
        "KLM Royal Dutch Airlines",
        "Korean Air",
        "Middle East Airlines",
        "Saudia",
        "TAROM",
        "Vietnam Airlines",
        "Virgin Atlantic",
        "XiamenAir",
    ],
}

IATA_TO_ALLIANCE: dict[str, str] = {
    "A3": "Star Alliance",
    "AC": "Star Alliance",
    "CA": "Star Alliance",
    "AI": "Star Alliance",
    "NZ": "Star Alliance",
    "NH": "Star Alliance",
    "OZ": "Star Alliance",
    "OS": "Star Alliance",
    "AV": "Star Alliance",
    "SN": "Star Alliance",
    "CM": "Star Alliance",
    "OU": "Star Alliance",
    "MS": "Star Alliance",
    "ET": "Star Alliance",
    "BR": "Star Alliance",
    "LO": "Star Alliance",
    "LH": "Star Alliance",
    "SK": "Star Alliance",
    "ZH": "Star Alliance",
    "SQ": "Star Alliance",
    "SA": "Star Alliance",
    "LX": "Star Alliance",
    "TP": "Star Alliance",
    "TG": "Star Alliance",
    "TK": "Star Alliance",
    "UA": "Star Alliance",
    "AS": "Oneworld",
    "AA": "Oneworld",
    "BA": "Oneworld",
    "CX": "Oneworld",
    "FJ": "Oneworld",
    "AY": "Oneworld",
    "IB": "Oneworld",
    "JL": "Oneworld",
    "MH": "Oneworld",
    "WY": "Oneworld",
    "QF": "Oneworld",
    "QR": "Oneworld",
    "AT": "Oneworld",
    "RJ": "Oneworld",
    "UL": "Oneworld",
    "AR": "SkyTeam",
    "AM": "SkyTeam",
    "UX": "SkyTeam",
    "AF": "SkyTeam",
    "CI": "SkyTeam",
    "MU": "SkyTeam",
    "OK": "SkyTeam",
    "DL": "SkyTeam",
    "GA": "SkyTeam",
    "AZ": "SkyTeam",
    "KQ": "SkyTeam",
    "KL": "SkyTeam",
    "KE": "SkyTeam",
    "ME": "SkyTeam",
    "SV": "SkyTeam",
    "RO": "SkyTeam",
    "VN": "SkyTeam",
    "VS": "SkyTeam",
    "MF": "SkyTeam",
}


def resolve_alliance_by_iata(iata_code: str | None) -> str | None:
    """Resolve alliance membership by IATA code."""
    if not iata_code:
        return None
    return IATA_TO_ALLIANCE.get(iata_code.upper())


def resolve_alliance_by_name(airline_name: str) -> str | None:
    """Resolve alliance membership by airline name (fuzzy match on canonical list)."""
    name_lower = airline_name.lower().strip()
    for alliance, members in ALLIANCE_MEMBERS.items():
        for member in members:
            if member.lower() in name_lower or name_lower in member.lower():
                return alliance
    return None
