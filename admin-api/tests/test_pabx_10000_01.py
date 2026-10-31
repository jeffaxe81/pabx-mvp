"""1.000 casos distintos: bloqueio de discagem e Unicode invisível."""
import pytest
from blocklist import validate_blocklist_number

@pytest.mark.parametrize("case", [
    pytest.param(i, id=f"AXE-{i+1:05d}") for i in range(1000)
])
def test_blocklist_1000_numbers_and_obfuscated_numbers(case):
    raw_number=str(1190000000+case)
    if case<500:
        # 500 números válidos; máscaras de apresentação variáveis.
        forms=(
            raw_number,
            f"({raw_number[:2]}) {raw_number[2:6]}-{raw_number[6:]}",
            f"+{raw_number[:2]} {raw_number[2:]}",
            f" {raw_number} ",
            f"{raw_number[:2]}.{raw_number[2:6]}.{raw_number[6:]}",
        )
        submitted=forms[case%len(forms)]
        assert validate_blocklist_number(submitted)==raw_number
    else:
        # 500 identificadores distintos com caractere de controle oculto.
        injection=("\u200b","\u200e","\u202e","\x00","\n")
        point=case%len(raw_number)
        submitted=(raw_number[:point]+injection[case%len(injection)]
                   +raw_number[point:])
        assert validate_blocklist_number(submitted) is None
