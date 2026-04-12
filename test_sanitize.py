from devrules.core.git_service import sanitize_text


def test_sanitize():
    cases = [
        ("mañana", "manana"),
        ("camión", "camion"),
        ("fútbol", "futbol"),
        ("niño", "nino"),
        ("Árbol", "arbol"),
        ("Crème Brûlée", "creme-brulee"),
        ("  espacios  ", "espacios"),
        ("multiple--hyphens", "multiple-hyphens"),
        ("weird@#$chars", "weird-chars"),
    ]

    for input_str, expected in cases:
        result = sanitize_text(input_str)
        print(
            f"Input: '{input_str}' -> Output: '{result}' | Expected: '{expected}' | {'PASS' if result == expected else 'FAIL'}"
        )


if __name__ == "__main__":
    test_sanitize()
