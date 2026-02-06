from __future__ import annotations

import re
from typing import Dict, List, Optional


def extract_features_from_text(
    text: str,
    features: List[str],
) -> Dict[str, Optional[str]]:
    """
    Generic regex-based feature extractor.

    - Handles standard patterns:  Feature : Value
    - Handles special case:
        VARIANTE FTS MOVE <name> AGV Underrider

    Returns:
        dict: feature -> extracted value (or None)
    """
    data: Dict[str, Optional[str]] = {}

    for feature in features:
        # Special case from your original code
        if feature.upper() == "VARIANTE FTS MOVE":
            pattern = rf"{re.escape(feature)}\s*([^\n\r]+?)\s*AGV\s*Underrider"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            data[feature] = match.group(1).strip() if match else None
            continue

        # Standard "Feature : Value" or "Feature:Value"
        pattern = rf"{re.escape(feature)}\s*[:\-]\s*([^\n\r]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        data[feature] = match.group(1).strip() if match else None

    return data
