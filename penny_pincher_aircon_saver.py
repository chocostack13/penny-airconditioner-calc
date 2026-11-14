# ==============================================================================
# 짠돌이의 에어컨 절약하기 (Penny-Pincher's Aircon Saver)
# - 실내 온도 예측 기반 에어컨 전력 소비 최적화 시뮬레이터
# 과목: 문제해결과 컴퓨팅사고 / 팀명: 사과나무 (2조)
#
# 실행 파일 (python penny_pincher_aircon_saver.py). 사용자 입력과 결과 출력만 담당한다.
#   aircon.py     : AirConditioner (에어컨 한 대)
#   aircon_db.py  : AirconDatabase (모델 DB, 시드 데이터)
#   simulator.py  : Simulator (전력량 계산)
#
# 모든 입력 함수는 올바른 값이 들어올 때까지 다시 묻는다.
# 표준 입력이 끝나면(Ctrl+Z/Ctrl+D) input()이 EOFError를 그대로 올려보낸다.
# ==============================================================================

import math
from collections.abc import Callable

from aircon import DEFAULT_MAKER, AirConditioner
from aircon_db import AirconDatabase
from simulator import MAX_OUT_MINUTES, SimulationResult, Simulator, recommend


def read_number(prompt: str, kind: Callable[[str], float] = float,
                min_value: float | None = None,
                max_value: float | None = None) -> float:
    """숫자 하나를 입력받는다.

    Args:
        prompt: 화면에 보여줄 질문.
        kind: 문자열을 숫자로 바꾸는 함수. float(기본) 또는 int.
            int를 주면 반환값도 int이다.
        min_value: 허용 최솟값 (포함). None이면 제한 없음.
        max_value: 허용 최댓값 (포함). None이면 제한 없음.

    Returns:
        min_value <= 값 <= max_value 를 만족하는 유한한 숫자 (nan, inf는 거부).

    Raises:
        EOFError: 입력이 끝났을 때.
    """
    while True:
        try:
            value = kind(input(prompt))
        except ValueError:
            print("  [입력 오류] 숫자로 입력해 주세요.")
            continue
        # int는 항상 유한하다. 아주 큰 int를 isfinite()에 넘기면 OverflowError가 나므로 float만 검사한다.
        if isinstance(value, float) and not math.isfinite(value):
            print("  [입력 오류] 숫자로 입력해 주세요.")
            continue
        if min_value is not None and value < min_value:
            print(f"  [입력 오류] {min_value} 이상의 값을 입력해 주세요.")
            continue
        if max_value is not None and value > max_value:
            print(f"  [입력 오류] {max_value} 이하의 값을 입력해 주세요.")
            continue
        return value


def ask_yes_no(prompt: str) -> bool:
    """예/아니오를 입력받는다.

    Returns:
        y·yes·예 이면 True, n·no·아니오 이면 False (대소문자 무시).

    Raises:
        EOFError: 입력이 끝났을 때.
    """
    while True:
        answer = input(f"{prompt} (y/n): ").strip().lower()
        if answer in ("y", "yes", "예", "ㅛ"):
            return True
        if answer in ("n", "no", "아니오", "ㅜ"):
            return False
        print("  [입력 오류] y 또는 n으로 입력해 주세요.")


def choose(title: str, options: list[str], allow_back: bool = False) -> int:
    """번호 메뉴를 보여주고 고른 번호를 돌려준다.

    Args:
        title: 메뉴 제목.
        options: 보여줄 항목들. 1번부터 차례로 번호가 붙는다. 비어 있으면 안 된다.
        allow_back: True면 0(뒤로가기)도 고를 수 있다.

    Returns:
        1 ~ len(options) 사이의 번호. allow_back이면 0도 가능.
        (options의 인덱스가 아니라 화면 번호이므로 options[번호 - 1]로 쓴다.)

    Raises:
        ValueError: options가 비어 있을 때.
        EOFError: 입력이 끝났을 때.
    """
    if not options:
        raise ValueError("메뉴 항목이 비어 있습니다.")
    print(f"\n[{title}]")
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    if allow_back:
        print("  0. 뒤로가기")
    return int(read_number("번호 선택: ", kind=int,
                           min_value=0 if allow_back else 1, max_value=len(options)))


def read_manual_air_conditioner(db: AirconDatabase) -> AirConditioner:
    """DB에 없는 에어컨을 직접 입력받고, 원하면 DB에도 저장한다.

    모델명을 비우면 '내 에어컨'으로 정하고 저장 여부는 묻지 않는다.

    Args:
        db: 저장할 때 쓸 열린 DB.

    Returns:
        검증을 통과한 AirConditioner (소비전력 단위 W).

    Raises:
        EOFError: 입력이 끝났을 때.
        sqlite3.Error: 저장 중 중복 외의 DB 오류가 났을 때.
    """
    print("\n[에어컨 직접 입력] (제품 사양표의 소비전력을 W 단위로 입력)")
    while True:
        maker = input("제조사 (예: 삼성, 비워두면 '기타'): ").strip() or DEFAULT_MAKER
        name = input("모델명 (예: AF17BX738ESN, 비워두면 '내 에어컨'): ").strip()
        rated = read_number("정격 냉방 소비전력 (W, 예: 2050): ", min_value=1)
        maintain = read_number("최소 냉방 소비전력 (W, 예: 300): ", min_value=1)
        try:
            ac = AirConditioner(name or "내 에어컨", rated, maintain, maker)
            break
        except ValueError as e:
            print(f"  [입력 오류] {e} 다시 입력해 주세요.\n")

    if name and ask_yes_no("이 모델을 DB에 저장해 다음부터 목록에서 고를 수 있게 할까요?"):
        if db.add(ac):
            print("  >> DB에 저장했습니다.")
        else:
            print("  >> 같은 제조사·모델명이 이미 DB에 있어 저장하지 않았습니다.")
    return ac


def read_air_conditioner(db: AirconDatabase) -> AirConditioner:
    """제조사 → 모델 순으로 DB에서 고르고, 없으면 '기타'에서 직접 입력받는다.

    모델 메뉴에서 0을 고르면 제조사 메뉴로 돌아간다.

    Args:
        db: 열린 DB.

    Returns:
        사용자가 고르거나 입력한 AirConditioner.

    Raises:
        EOFError: 입력이 끝났을 때.
        sqlite3.Error: DB 조회·저장에 실패했을 때.
    """
    while True:
        makers = db.makers()
        choice = choose("제조사 선택", makers + [f"{DEFAULT_MAKER} (목록에 없음, 직접 입력)"])
        if choice == len(makers) + 1:
            return read_manual_air_conditioner(db)

        maker = makers[choice - 1]
        models = db.models_by_maker(maker)
        labels = [f"{m.name}  [정격 {m.rated:g}W / 최소 {m.maintain:g}W]" for m in models]
        pick = choose(f"{maker} 모델 선택", labels, allow_back=True)
        if pick != 0:
            return models[pick - 1]


def read_simulator() -> Simulator:
    """외출 상황을 입력받아 Simulator를 만든다.

    Returns:
        온도는 ℃, 외출 시간은 0 이상의 정수(분)로 채워진 Simulator.

    Raises:
        EOFError: 입력이 끝났을 때.
    """
    print("\n[외출 상황 입력]")
    current_temp = read_number("1. 현재 실내 온도 (℃, 예: 25.5): ")
    outdoor_temp = read_number("2. 현재 실외 온도 (℃, 예: 31.0): ")
    target_temp = read_number("3. 희망 설정 온도 (℃, 예: 24.0): ")
    out_minutes = int(read_number("4. 외출 예정 시간 (분, 예: 45): ", kind=int,
                                  min_value=0, max_value=MAX_OUT_MINUTES))
    return Simulator(current_temp, outdoor_temp, target_temp, out_minutes)


def print_result(ac: AirConditioner, result: SimulationResult, short_trip: bool) -> None:
    """결과와 추천을 화면에 출력한다. 반환값·예외 없음.

    Args:
        ac: 계산에 쓴 에어컨 (이름과 비고를 표시).
        result: Simulator.run()의 결과 (전력량 단위 Wh).
        short_trip: True면 전력량과 관계없이 '켜두기'를 추천한다.
            (켜두는 쪽이 전력을 더 쓰면 그 차이를 '추가 소비'로 안내한다.)
    """
    print("\n" + "=" * 60)
    print("                   [ 시뮬레이션 결과 ]")
    print("=" * 60)
    print(f"• 선택된 기종              : {ac.display_name}")
    if ac.note:
        print(f"  ※ {ac.note}")
    print(f"• 귀가 시 예상 실내 온도   : {result.predicted_temp:.1f} ℃")
    print(f"• 에어컨 유지 시 총 소비전력 : {result.keep_power:.1f} Wh")
    print(f"• 에어컨 재가동 시 소비전력  : {result.restart_power:.1f} Wh")
    print("-" * 60)

    rec = recommend(result, short_trip)
    print(f">> [최적 제안] {rec.title}")
    print(f"   {rec.detail}")
    print("=" * 60)


def main() -> None:
    print("=" * 60)
    print("            [ 짠돌이의 에어컨 절약하기 ]")
    print("    실내 온도 예측 기반 에어컨 전력 최적화 시뮬레이터")
    print("=" * 60)

    simulator = read_simulator()
    with AirconDatabase() as db:
        ac = read_air_conditioner(db)
    result = simulator.run(ac)
    print_result(ac, result, simulator.is_short_trip())


if __name__ == "__main__":
    main()
