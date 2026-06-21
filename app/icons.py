#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ASL-3D - Icons, Colors, and Text definitions for patholgies and severity.
"""

class Icons:
    FISSURES = 'ph-duotone ph-warning-octagon'
    HUMIDITY = 'ph-duotone ph-drop'
    EROSION = 'ph-duotone ph-wind'
    FUNGI = 'ph-duotone ph-bug'
    DISCOLORATION = 'ph-duotone ph-palette'
    CRUMBLING = 'ph-duotone ph-squares-four'

class IconColors:
    CRITICAL = '#ff6b6b'
    HIGH = '#ffa36c'
    MEDIUM = '#6c63ff'
    LOW = '#ffd166'

class IconText:
    SEVERITY_LEVELS = {
        'haute': 'Haute',
        'moyenne': 'Moyenne',
        'basse': 'Basse'
    }
