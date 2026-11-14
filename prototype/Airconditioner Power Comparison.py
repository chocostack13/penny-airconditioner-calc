# ==============================================================================
# 실내 온도 예측 기반 에어컨 전력 소비 최적화 시뮬레이터
# 과목: 문제해결과 컴퓨팅사고 / 팀명: 사과나무 (2조)
# ==============================================================================

# 제조사별 대표 가정용 스탠드 에어컨(17~18평형) 소비전력 데이터 (단위: W)
# - rated: 정격 냉방 소비전력 (외출 복귀 후 실내 온도를 급속 냉방할 때 가동)
# - maintain: 최소 냉방 소비전력 (설정 온도를 일정하게 유지할 때 가동)
# 출처: 삼성전자·LG전자 공식 제품 페이지, 캐리어 판매처 사양표
AC_SPECS = {
    "samsung": {
        "name": "삼성 비스포크 무풍 갤러리 스탠드 17평형 (AF17BX738ESN)",
        "rated": 2050,
        "maintain": 300
    },
    "lg": {
        "name": "LG 휘센 오브제컬렉션 위너 스탠드 18평형 (FQ18HDWHY1)",
        "rated": 2200,
        "maintain": 320
    },
    "carrier": {
        "name": "캐리어 에어로 18단 스탠드 18평형 (CPV-Q181ML)",
        "rated": 2050,
        "maintain": 330  # 최소 소비전력은 공개 사양표에 없어 동급 모델을 참고한 추정값
    }
}

def calculate_simulation(current_temp, outdoor_temp, target_temp, out_minutes, spec):
    """
    사용자 입력 데이터를 바탕으로 유지 전력량, 복귀 시 실내 온도, 재냉방 전력량을 계산합니다.
    """
    hours = out_minutes / 60.0

    # 1. 에어컨을 껐을 때: 외기와의 온도차 및 외출 시간에 따른 실내 온도 상승 예측
    temp_gap = outdoor_temp - current_temp

    # 실외 온도가 실내보다 높을 경우 실내 온도가 서서히 상승 (열전달 단순화 모델)
    if temp_gap > 0:
        # 시간당 온도차의 약 15% 수준으로 실내 온도가 점진적 상승 (단, 실외 기온을 넘지 않음)
        predicted_temp = current_temp + (temp_gap * 0.15 * hours)
        if predicted_temp > outdoor_temp:
            predicted_temp = outdoor_temp
    else:
        # 실외가 더 선선하거나 같을 경우 온도는 거의 상승하지 않음
        predicted_temp = current_temp

    # 2. 귀가 후 목표 온도까지 다시 냉방하는 데 필요한 예상 시간(시간) 및 전력량(Wh)
    cooling_needed = max(0.0, predicted_temp - target_temp)
    # 1도 낮추는 데 약 7분 소요된다고 가정한 단순 냉방 모델
    # (한국소비자원: 18평형 에어컨으로 35℃→26℃ 냉방에 약 1시간 → 1℃당 약 6~7분)
    cooling_hours = cooling_needed * (7 / 60.0)
    restart_power = spec["rated"] * cooling_hours

    # 3. 에어컨을 끄지 않고 유지할 때 총 소비전력량 (Wh)
    # 두 방식을 같은 시간 구간(외출 시간 + 재냉방 시간)으로 비교하기 위해
    # 귀가 후 재냉방 시간 동안에도 유지 전력으로 계속 가동한다고 본다.
    keep_power = spec["maintain"] * (hours + cooling_hours)

    # 절감 전력량 계산
    saved_power = abs(keep_power - restart_power)

    return keep_power, predicted_temp, restart_power, saved_power

def main():
    print("=" * 60)
    print("    [실내 온도 예측 기반 에어컨 전력 최적화 시뮬레이터]")
    print("=" * 60)

    try:
        # 1. 사용자 데이터 입력 (형변환 적용)
        current_temp = float(input("1. 현재 실내 온도를 입력하세요 (℃, 예: 25.5): "))
        outdoor_temp = float(input("2. 현재 실외 온도를 입력하세요 (℃, 예: 31.0): "))
        target_temp = float(input("3. 희망 설정 온도를 입력하세요 (℃, 예: 24.0): "))
        out_minutes = int(input("4. 외출 예정 시간(분)을 입력하세요 (예: 45): "))

        print("\n[에어컨 모델 선택]")
        for key, spec in AC_SPECS.items():
            print(f"  - {key:<7} : {spec['name']}")
        ac_type = input("선택할 제조사를 입력하세요 (samsung / lg / carrier): ").strip().lower()

        # 딕셔너리의 get() 메소드를 활용한 예외 안전 매핑
        selected_spec = AC_SPECS.get(ac_type, AC_SPECS["samsung"])
        print(f">> 선택된 기종: {selected_spec['name']}")

        # 연산 수행
        keep_power, predicted_temp, restart_power, saved_power = calculate_simulation(
            current_temp, outdoor_temp, target_temp, out_minutes, selected_spec
        )

        print("\n" + "=" * 60)
        print("                   [ 시뮬레이션 결과 ]")
        print("=" * 60)
        print(f"• 귀가 시 예상 실내 온도   : {predicted_temp:.1f} ℃")
        print(f"• 에어컨 유지 시 총 소비전력 : {keep_power:.1f} Wh")
        print(f"• 에어컨 재가동 시 소비전력  : {restart_power:.1f} Wh")
        print("-" * 60)

        # 4. 핵심 조건 분기 (선택문 적용)
        if out_minutes <= 20 or keep_power < restart_power:
            print(">> [최적 제안] 에어컨을 끄지 않고 '그대로 켜두는 것'이 유리합니다!")
            print(f"   외출 시간이 짧거나 유지 전력이 더 적어 약 {saved_power:.1f} Wh의 전력을 절약할 수 있습니다.")
        elif keep_power > restart_power:
            print(">> [최적 제안] 외출 시 에어컨을 '끄고 나가는 것'이 훨씬 경제적입니다!")
            print(f"   에어컨을 끄고 외출 시 약 {saved_power:.1f} Wh의 전력을 아낄 수 있습니다.")
        else:
            print(">> [최적 제안] 두 방식의 전력 소비 차이가 거의 없습니다.")
            print("   쾌적한 실내 환경 유지를 위해 가동 상태를 유지하는 것을 권장합니다.")
        print("=" * 60)

    except ValueError:
        print("\n[입력 오류] 숫자(정수 또는 소수점)로 정확하게 입력해 주세요!")

if __name__ == "__main__":
    main()