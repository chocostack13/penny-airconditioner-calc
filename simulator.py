"""'켜두기' vs '끄고 나가기' 전력량 계산.

입출력 없이 계산만 한다.
"""

from dataclasses import dataclass

from aircon import AirConditioner

# 시뮬레이션에 쓰는 가정값
HEAT_RATE: float = 0.15          # 시간당 (실외-실내) 온도차의 15%만큼 실내 온도가 상승 (1/h)
MINUTES_PER_DEGREE: float = 7    # 1℃ 낮추는 데 걸리는 시간 (분/℃)
                                 # (한국소비자원: 18평형 에어컨으로 35℃→26℃ 냉방에 약 1시간)
SHORT_OUT_MINUTES: int = 20      # 이 시간(분) 이하의 외출이면 무조건 켜두는 편이 유리하다고 본다
MAX_OUT_MINUTES: int = 24 * 60   # 입력받을 수 있는 최대 외출 시간 (분)


@dataclass
class SimulationResult:
    """시뮬레이션 한 번의 계산 결과. 모든 값은 0 이상."""
    predicted_temp: float   # 귀가 시 예상 실내 온도 (℃)
    keep_power: float       # 에어컨을 켜두었을 때 총 소비전력량 (Wh)
    restart_power: float    # 껐다가 재가동할 때 소비전력량 (Wh)
    saved_power: float      # 두 방식의 차이의 절댓값 (Wh)


class Simulator:
    """외출 상황(실내·실외·목표 온도, 외출 시간)을 기억하고 에어컨별로 계산한다.

    같은 상황에서 run()에 에어컨만 바꿔 넣으면 여러 모델을 비교할 수 있다.
    """

    def __init__(self, current_temp: float, outdoor_temp: float,
                 target_temp: float, out_minutes: int) -> None:
        """
        Args:
            current_temp: 현재 실내 온도 (℃).
            outdoor_temp: 현재 실외 온도 (℃).
            target_temp: 귀가 후 희망 설정 온도 (℃).
            out_minutes: 외출 시간 (분). 0 이상 MAX_OUT_MINUTES 이하여야 함.

        Raises:
            ValueError: out_minutes가 음수이거나 MAX_OUT_MINUTES보다 클 때.
        """
        if out_minutes < 0:
            raise ValueError("외출 시간은 0분 이상이어야 합니다.")
        if out_minutes > MAX_OUT_MINUTES:
            raise ValueError(f"외출 시간은 {MAX_OUT_MINUTES}분 이하여야 합니다.")
        self.current_temp: float = current_temp
        self.outdoor_temp: float = outdoor_temp
        self.target_temp: float = target_temp
        self.out_minutes: int = out_minutes
        self.hours: float = out_minutes / 60.0

    def predict_indoor_temp(self) -> float:
        """에어컨을 껐을 때 귀가 시점의 실내 온도를 예측한다 (열전달 단순화 모델).

        Returns:
            예상 실내 온도 (℃). 항상 current_temp 이상, 그리고
            실외가 더 더우면 outdoor_temp 이하. 예외 없음.
        """
        temp_gap = self.outdoor_temp - self.current_temp
        if temp_gap <= 0:
            # 실외가 더 선선하거나 같으면 온도는 거의 오르지 않음
            return self.current_temp
        predicted = self.current_temp + temp_gap * HEAT_RATE * self.hours
        return min(predicted, self.outdoor_temp)  # 실외 기온을 넘지 않음

    def run(self, ac: AirConditioner) -> SimulationResult:
        """주어진 에어컨으로 '켜두기'와 '끄고 나가기'의 전력량(Wh)을 비교한다.

        두 방식을 같은 구간(외출 시간 + 재냉방 시간)으로 비교한다.

        Args:
            ac: 계산에 쓸 에어컨 (생성 시점에 검증된 객체).

        Returns:
            SimulationResult. 예외 없음.
        """
        predicted_temp = self.predict_indoor_temp()

        # 귀가 후 목표 온도까지 다시 냉방하는 데 필요한 시간(h)과 전력량(Wh)
        cooling_needed = max(0.0, predicted_temp - self.target_temp)
        cooling_hours = cooling_needed * (MINUTES_PER_DEGREE / 60.0)
        restart_power = ac.rated * cooling_hours

        # 켜두는 경우: 현재 온도가 목표보다 높으면 먼저 정격 전력으로 목표 온도까지
        # 냉방하고, 남은 구간은 최소 전력으로 유지한다.
        # predicted_temp >= current_temp 이므로 initial_hours <= cooling_hours 이고,
        # 남은 구간(hours + cooling_hours - initial_hours)은 0 이상이다.
        initial_needed = max(0.0, self.current_temp - self.target_temp)
        initial_hours = initial_needed * (MINUTES_PER_DEGREE / 60.0)
        keep_power = (ac.rated * initial_hours
                      + ac.maintain * (self.hours + cooling_hours - initial_hours))

        return SimulationResult(
            predicted_temp=predicted_temp,
            keep_power=keep_power,
            restart_power=restart_power,
            saved_power=abs(keep_power - restart_power),
        )

    def is_short_trip(self) -> bool:
        """외출 시간이 SHORT_OUT_MINUTES(분) 이하이면 True."""
        return self.out_minutes <= SHORT_OUT_MINUTES


@dataclass
class Recommendation:
    """추천 결과. 콘솔과 GUI가 같은 문구를 쓰도록 여기서 만든다."""
    keep_on: bool   # True면 '켜두기', False면 '끄고 나가기' 추천
    title: str      # 한 줄 요약
    detail: str     # 근거 설명 (전력량 단위 Wh)


def recommend(result: SimulationResult, short_trip: bool) -> Recommendation:
    """계산 결과로 추천을 정한다.

    규칙: 켜두는 쪽이 적게 쓰면 켜두기. 외출이 짧으면(short_trip)
    전력이 더 들어도 쾌적함을 위해 켜두기. 그 외에 켜두는 쪽이 많이 쓰면 끄기.
    같으면 켜두기.

    Args:
        result: Simulator.run()의 결과.
        short_trip: Simulator.is_short_trip()의 값.

    Returns:
        Recommendation. 예외 없음.
    """
    diff = result.saved_power
    if result.keep_power < result.restart_power:
        return Recommendation(True, "에어컨을 끄지 않고 '그대로 켜두는 것'이 유리합니다!",
                              f"유지 전력이 더 적어 약 {diff:.1f} Wh의 전력을 절약할 수 있습니다.")
    if short_trip:
        return Recommendation(True, "외출 시간이 짧아 '그대로 켜두는 것'을 권장합니다.",
                              f"전력은 약 {diff:.1f} Wh 더 들지만, 귀가 후 바로 쾌적합니다.")
    if result.keep_power > result.restart_power:
        return Recommendation(False, "외출 시 에어컨을 '끄고 나가는 것'이 훨씬 경제적입니다!",
                              f"에어컨을 끄고 외출 시 약 {diff:.1f} Wh의 전력을 아낄 수 있습니다.")
    return Recommendation(True, "두 방식의 전력 소비 차이가 거의 없습니다.",
                          "쾌적한 실내 환경 유지를 위해 가동 상태를 유지하는 것을 권장합니다.")
