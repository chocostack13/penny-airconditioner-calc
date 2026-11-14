# ==============================================================================
# 짠돌이의 에어컨 절약하기 (Penny-Pincher's Aircon Saver) - GUI 버전
# 과목: 문제해결과 컴퓨팅사고 / 팀명: 사과나무 (2조)
#
# 실행: python penny_pincher_gui.py
# 콘솔 버전(penny_pincher_aircon_saver.py)과 같은 계산·DB 코드를 쓰고, 화면만 tkinter로 만든다.
# ==============================================================================

import math
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from aircon import DEFAULT_MAKER, AirConditioner
from aircon_db import AirconDatabase
from simulator import MAX_OUT_MINUTES, SimulationResult, Simulator, recommend

MANUAL_CHOICE: str = f"{DEFAULT_MAKER} (직접 입력)"
FONT: str = "맑은 고딕"
KEEP_COLOR: str = "#2b7bb9"     # '켜두기' 막대 색
RESTART_COLOR: str = "#e07b39"  # '재가동' 막대 색


def parse_number(text: str, label: str, min_value: float | None = None,
                 integer: bool = False, max_value: float | None = None) -> float:
    """입력칸의 문자열을 숫자로 바꾼다.

    Args:
        text: 입력칸 내용. 앞뒤 공백은 무시한다.
        label: 오류 메시지에 쓸 항목 이름 (예: '실내 온도').
        min_value: 허용 최솟값 (포함). None이면 제한 없음.
        integer: True면 정수만 허용하고 int를 돌려준다.
        max_value: 허용 최댓값 (포함). None이면 제한 없음.

    Returns:
        유한한 숫자 (integer면 int).

    Raises:
        ValueError: 숫자가 아니거나, nan/inf이거나, min_value~max_value 범위를 벗어날 때.
            메시지는 사용자에게 그대로 보여줄 수 있는 한국어 문장이다.
    """
    try:
        value: float = int(text.strip()) if integer else float(text.strip())
    except ValueError:
        kind = "정수" if integer else "숫자"
        raise ValueError(f"'{label}'에는 {kind}를 입력해 주세요.") from None
    # int는 항상 유한하다. 아주 큰 int를 isfinite()에 넘기면 OverflowError가 나므로 float만 검사한다.
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"'{label}'에는 숫자를 입력해 주세요.")
    if min_value is not None and value < min_value:
        raise ValueError(f"'{label}'은(는) {min_value:g} 이상이어야 합니다.")
    if max_value is not None and value > max_value:
        raise ValueError(f"'{label}'은(는) {max_value:g} 이하여야 합니다.")
    return value


class AirconApp:
    """메인 창. 입력(외출 상황·에어컨) → 계산 → 결과(문구·막대그래프)를 보여준다.

    창이 열려 있는 동안 DB 연결과 현재 선택된 모델 목록을 상태로 유지하고,
    창을 닫을 때 DB 연결을 닫는다.
    """

    def __init__(self, root: tk.Tk, db: AirconDatabase) -> None:
        """
        Args:
            root: tkinter 최상위 창.
            db: 열린 DB. 창이 닫힐 때 이 클래스가 닫는다.
        """
        self.root = root
        self.db = db
        self.models: list[AirConditioner] = []  # 현재 제조사의 모델 목록

        root.title("짠돌이의 에어컨 절약하기")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style()
        style.configure(".", font=(FONT, 10))
        style.configure("Title.TLabel", font=(FONT, 16, "bold"))
        style.configure("Big.TLabel", font=(FONT, 11, "bold"))
        style.configure("Calc.TButton", font=(FONT, 11, "bold"), padding=6)

        main = ttk.Frame(root, padding=14)
        main.grid()

        ttk.Label(main, text="짠돌이의 에어컨 절약하기", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(main, text="외출할 때 에어컨, 켜둘까? 끄고 나갈까?").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        left = ttk.Frame(main)
        left.grid(row=2, column=0, sticky="n", padx=(0, 14))
        self._build_situation(left)
        self._build_aircon(left)
        ttk.Button(left, text="계산하기", style="Calc.TButton",
                   command=self.calculate).grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self._build_result(main)
        self._load_makers()

    # ------------------------------------------------------------------
    # 화면 구성
    # ------------------------------------------------------------------

    def _build_situation(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text=" 1. 외출 상황 ", padding=10)
        box.grid(row=0, column=0, sticky="ew")
        self.situation_vars: dict[str, tk.StringVar] = {}
        fields = [("current", "현재 실내 온도 (℃)", "25.5"),
                  ("outdoor", "현재 실외 온도 (℃)", "31.0"),
                  ("target", "희망 설정 온도 (℃)", "24.0"),
                  ("minutes", "외출 시간 (분)", "45")]
        for row, (key, label, default) in enumerate(fields):
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=default)
            ttk.Entry(box, textvariable=var, width=10, justify="right").grid(
                row=row, column=1, sticky="e", padx=(10, 0), pady=2)
            self.situation_vars[key] = var

    def _build_aircon(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text=" 2. 에어컨 선택 ", padding=10)
        box.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(box, text="제조사").grid(row=0, column=0, sticky="w", pady=2)
        self.maker_box = ttk.Combobox(box, state="readonly", width=34)
        self.maker_box.grid(row=0, column=1, sticky="ew", pady=2)
        self.maker_box.bind("<<ComboboxSelected>>", lambda _e: self._on_maker_selected())

        ttk.Label(box, text="모델").grid(row=1, column=0, sticky="w", pady=2)
        self.model_box = ttk.Combobox(box, state="readonly", width=44)
        self.model_box.grid(row=1, column=1, sticky="ew", pady=2)
        self.model_box.bind("<<ComboboxSelected>>", lambda _e: self._show_spec())

        self.spec_label = ttk.Label(box, text="", foreground="#555", wraplength=300)
        self.spec_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # '기타' 선택 시에만 보이는 직접 입력칸
        self.manual_frame = ttk.Frame(box)
        self.manual_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.manual_vars: dict[str, tk.StringVar] = {}
        fields = [("maker", "제조사", ""), ("name", "모델명", ""),
                  ("rated", "정격 냉방 소비전력 (W)", ""),
                  ("maintain", "최소 냉방 소비전력 (W)", "")]
        for row, (key, label, default) in enumerate(fields):
            ttk.Label(self.manual_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=default)
            ttk.Entry(self.manual_frame, textvariable=var, width=20).grid(
                row=row, column=1, sticky="e", padx=(10, 0), pady=2)
            self.manual_vars[key] = var
        ttk.Button(self.manual_frame, text="이 모델을 DB에 저장",
                   command=self.save_manual).grid(row=4, column=1, sticky="e", pady=(4, 0))

    def _build_result(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text=" 3. 결과 ", padding=10)
        box.grid(row=2, column=1, sticky="nsew")

        self.result_vars: dict[str, tk.StringVar] = {}
        rows = [("ac", "선택된 기종"), ("temp", "귀가 시 예상 실내 온도"),
                ("keep", "켜두기 총 소비전력"), ("restart", "끄고 재가동 소비전력")]
        for row, (key, label) in enumerate(rows):
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="nw", pady=2)
            var = tk.StringVar(value="-")
            ttk.Label(box, textvariable=var, style="Big.TLabel", wraplength=230).grid(
                row=row, column=1, sticky="w", padx=(10, 0), pady=2)
            self.result_vars[key] = var

        self.note_label = ttk.Label(box, text="", foreground="#888", wraplength=380)
        self.note_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 6))

        self.chart = tk.Canvas(box, width=380, height=130, bg="white",
                               highlightthickness=1, highlightbackground="#ccc")
        self.chart.grid(row=5, column=0, columnspan=2, pady=(0, 8))

        self.rec_title = tk.Label(box, text="값을 입력하고 [계산하기]를 누르세요.",
                                  font=(FONT, 12, "bold"), wraplength=380, justify="left")
        self.rec_title.grid(row=6, column=0, columnspan=2, sticky="w")
        self.rec_detail = ttk.Label(box, text="", wraplength=380)
        self.rec_detail.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # 에어컨 선택
    # ------------------------------------------------------------------

    def _load_makers(self, select: str | None = None) -> None:
        """DB에서 제조사 목록을 다시 읽는다. select가 있으면 그 제조사를 고른다."""
        makers = self.db.makers()
        self.maker_box["values"] = makers + [MANUAL_CHOICE]
        self.maker_box.set(select if select in makers else (makers[0] if makers else MANUAL_CHOICE))
        self._on_maker_selected()

    def _on_maker_selected(self) -> None:
        maker = self.maker_box.get()
        if maker == MANUAL_CHOICE:
            self.models = []
            self.model_box.set("")
            self.model_box.state(["disabled"])
            self.spec_label.config(text="제품 사양표의 소비전력을 W 단위로 입력하세요.")
            self.manual_frame.grid()
            return
        self.manual_frame.grid_remove()
        self.model_box.state(["!disabled", "readonly"])
        self.models = self.db.models_by_maker(maker)
        self.model_box["values"] = [m.name for m in self.models]
        self.model_box.current(0)
        self._show_spec()

    def _show_spec(self) -> None:
        ac = self.models[self.model_box.current()]
        self.spec_label.config(text=f"정격 {ac.rated:g}W / 최소 {ac.maintain:g}W\n※ {ac.note}")

    def _manual_aircon(self) -> AirConditioner:
        """직접 입력칸으로 AirConditioner를 만든다.

        Raises:
            ValueError: 소비전력이 숫자가 아니거나 규칙(0 < 최소 <= 정격)을 어길 때.
        """
        v = self.manual_vars
        rated = parse_number(v["rated"].get(), "정격 냉방 소비전력", min_value=1)
        maintain = parse_number(v["maintain"].get(), "최소 냉방 소비전력", min_value=1)
        return AirConditioner(v["name"].get().strip() or "내 에어컨", rated, maintain,
                              v["maker"].get().strip() or DEFAULT_MAKER)

    def selected_aircon(self) -> AirConditioner:
        """현재 화면에서 고르거나 입력한 에어컨.

        Raises:
            ValueError: '기타'의 입력값이 잘못됐을 때.
        """
        if self.maker_box.get() == MANUAL_CHOICE:
            return self._manual_aircon()
        return self.models[self.model_box.current()]

    def save_manual(self) -> None:
        """직접 입력한 모델을 DB에 저장하고, 목록에서 그 모델을 고른다."""
        if not self.manual_vars["name"].get().strip():
            messagebox.showwarning("저장 불가", "저장하려면 모델명을 입력해 주세요.")
            return
        try:
            ac = self._manual_aircon()
        except ValueError as e:
            messagebox.showerror("입력 오류", str(e))
            return
        try:
            added = self.db.add(ac)
        except sqlite3.Error as e:
            messagebox.showerror("저장 실패", f"DB에 저장하지 못했습니다.\n({e})")
            return
        if not added:
            messagebox.showinfo("저장 안 함", "같은 제조사·모델명이 이미 DB에 있습니다.")
            return
        messagebox.showinfo("저장 완료", f"'{ac.display_name}'을(를) DB에 저장했습니다.")
        self._load_makers(select=ac.maker)
        self.model_box.current(len(self.models) - 1)
        self._show_spec()

    # ------------------------------------------------------------------
    # 계산과 결과
    # ------------------------------------------------------------------

    def read_simulator(self) -> Simulator:
        """외출 상황 입력칸으로 Simulator를 만든다.

        Raises:
            ValueError: 입력값이 숫자가 아니거나 외출 시간이 음수일 때.
        """
        v = self.situation_vars
        return Simulator(
            parse_number(v["current"].get(), "현재 실내 온도"),
            parse_number(v["outdoor"].get(), "현재 실외 온도"),
            parse_number(v["target"].get(), "희망 설정 온도"),
            int(parse_number(v["minutes"].get(), "외출 시간", min_value=0, integer=True,
                             max_value=MAX_OUT_MINUTES)),
        )

    def calculate(self) -> None:
        """[계산하기] 버튼. 잘못된 입력은 오류 창으로 알리고 결과는 그대로 둔다."""
        try:
            simulator = self.read_simulator()
            ac = self.selected_aircon()
        except ValueError as e:
            messagebox.showerror("입력 오류", str(e))
            return
        result = simulator.run(ac)
        self.show_result(ac, result, simulator.is_short_trip())

    def show_result(self, ac: AirConditioner, result: SimulationResult, short_trip: bool) -> None:
        self.result_vars["ac"].set(ac.display_name)
        self.result_vars["temp"].set(f"{result.predicted_temp:.1f} ℃")
        self.result_vars["keep"].set(f"{result.keep_power:.1f} Wh")
        self.result_vars["restart"].set(f"{result.restart_power:.1f} Wh")
        self.note_label.config(text=f"※ {ac.note}" if ac.note else "")

        rec = recommend(result, short_trip)
        self.rec_title.config(text=("👍 " if rec.keep_on else "🔌 ") + rec.title,
                              fg=KEEP_COLOR if rec.keep_on else RESTART_COLOR)
        self.rec_detail.config(text=rec.detail)
        self.draw_chart(result)

    def draw_chart(self, result: SimulationResult) -> None:
        """두 방식의 소비전력량(Wh)을 가로 막대그래프로 그린다."""
        c = self.chart
        c.delete("all")
        width = int(c["width"])
        label_w, value_w, pad = 90, 80, 12
        bar_max = width - label_w - value_w - pad
        top = max(result.keep_power, result.restart_power, 1e-9)
        bars = [("켜두기", result.keep_power, KEEP_COLOR),
                ("끄고 재가동", result.restart_power, RESTART_COLOR)]
        c.create_text(pad, 14, text="소비전력량 비교 (Wh)", anchor="w", font=(FONT, 9, "bold"))
        for i, (label, value, color) in enumerate(bars):
            y = 40 + i * 45
            length = bar_max * value / top
            c.create_text(label_w - 8, y + 12, text=label, anchor="e", font=(FONT, 10))
            c.create_rectangle(label_w, y, label_w + max(length, 1), y + 24, fill=color, width=0)
            c.create_text(label_w + length + 6, y + 12, text=f"{value:.1f}",
                          anchor="w", font=(FONT, 10, "bold"))

    def close(self) -> None:
        self.db.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AirconApp(root, AirconDatabase())
    root.mainloop()


if __name__ == "__main__":
    main()
