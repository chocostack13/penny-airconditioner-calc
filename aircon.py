"""에어컨 한 대를 나타내는 클래스.

DB(aircon_db.py)와 계산(simulator.py)이 함께 쓰므로 따로 둔다.
"""

DEFAULT_MAKER: str = "기타"


class AirConditioner:
    """에어컨 한 대의 제조사·모델명·소비전력.

    제품마다 같은 구조에 값만 다르므로 클래스로 묶고,
    잘못된 값은 만들어지는 시점에 걸러낸다. 만들어진 객체는 항상
    0 < maintain <= rated 를 만족한다.
    """

    def __init__(self, name: str, rated: float, maintain: float,
                 maker: str = DEFAULT_MAKER, note: str = "") -> None:
        """
        Args:
            name: 모델명. 빈 문자열도 허용하지만 화면 표시용이므로 채우는 것을 권장.
            rated: 정격 냉방 소비전력 (W). 복귀 후 급속 냉방할 때 사용. 0보다 커야 함.
            maintain: 최소 냉방 소비전력 (W). 설정 온도를 유지할 때 사용.
                0보다 크고 rated 이하여야 함.
            maker: 제조사. 기본값은 '기타'.
            note: 데이터 출처·추정 여부 등 비고. 결과 화면에 그대로 표시된다.

        Raises:
            ValueError: rated 또는 maintain이 0 이하이거나, maintain > rated일 때.
                메시지는 사용자에게 그대로 보여줄 수 있는 한국어 문장이다.
        """
        if rated <= 0 or maintain <= 0:
            raise ValueError("소비전력은 0보다 커야 합니다.")
        if maintain > rated:
            raise ValueError("최소(유지) 소비전력이 정격 소비전력보다 클 수 없습니다.")
        self.maker: str = maker
        self.name: str = name
        self.rated: float = rated
        self.maintain: float = maintain
        self.note: str = note

    @property
    def display_name(self) -> str:
        """화면 표시용 이름. '제조사 모델명' 형식."""
        return f"{self.maker} {self.name}"
