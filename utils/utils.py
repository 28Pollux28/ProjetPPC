from typing import List


def convertArrayToBinary(array: List[int]) -> int:
    return int(''.join(str(e) for e in array), 2)


def convertDecimalToBinary(number: int) -> List[int]:
    return [int(e) for e in bin(number)[2:]]

