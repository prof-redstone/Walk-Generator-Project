# Walk-Generator-Project

## Project Summary

**Walk-Generator-Project** is an initiative to create a smart routing application that generates high-quality walking paths tailored to user-defined time or distance constraints. Unlike standard navigation, this project prioritizes the **enjoyability and safety** of the journey by selecting street segments based on aesthetic, cultural, and accessibility criteria.

---

## Core Goals & Features

The primary function is to transform a simple time or distance request into a curated walking experience.

### Routing Capabilities
* **Constraint-Based Generation:** Routes are precisely mapped to meet the user's requested duration or length.
* **Flexible Pathing:** Supports generation of both **closed loops** (starting and ending at the same point) and **point-to-point paths** (A to B).
* **Loop Optimization:** Paths are designed to avoid repetition and maximize the area covered, ensuring a diverse and engaging walk.

### Street Quality Prioritization
Routes are generated using a sophisticated scoring system that favors segments based on the following qualitative metrics:

* **Aesthetics & Culture:** Presence of engaging architecture, greenery, and cultural points of interest.
* **Safety & Serenity:** Streets with a high perceived sense of safety and calm.
* **Accessibility:** Ease of travel, including consideration for individuals with mobility challenges (e.g., smooth paths, gentle slopes).
* **Terrain:** Analysis of elevation changes (*dénivelé*) to match user preference.

---

## Technical Approach

### Street Scoring and Heuristics
Each segment in the map network receives a dynamic quality assessment. This score is determined by a **heuristic model (likely a Neural Network)** that synthesizes various map data points (e.g., tree cover, building type, road width) and essential **user feedback** to accurately predict the walkability and appeal of a street.

### Data Strategy
To train our quality model, we are compiling data from several sources:
1.  **Open Source Mapping:** Leveraging existing map data with custom analysis and labeling.
2.  **User Ratings:** Implementing client feedback mechanisms to rate walks, providing real-world validation.
3.  **Curated Paths:** Integrating and analyzing known high-quality routes (e.g., popular trails, hiking paths) as a quality baseline.