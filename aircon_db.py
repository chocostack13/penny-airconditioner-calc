"""에어컨 모델 DB (SQLite).

SQL과 시드 데이터는 이 파일 안에서만 다룬다.
다른 파일은 AirconDatabase의 메서드로만 DB에 접근한다.
"""

import sqlite3
from pathlib import Path
from types import TracebackType

from aircon import AirConditioner

DB_PATH: Path = Path(__file__).with_name("aircon.db")  # 이 파일과 같은 폴더에 생성된다

# 비고 문구
_OFFICIAL = "공식 사양"
_PARTIAL = "정격은 공개 사양, 최소 소비전력은 동급 모델을 참고한 추정값"
_FAKE = "가상 데이터: 동급 평형 기준으로 만든 추정값 (실제 사양 아님)"

# DB에 들어가는 대표 모델 (단위: W)
# (제조사, 모델명, 정격 냉방 소비전력, 최소 냉방 소비전력, 비고)
SEED_MODELS: list[tuple[str, str, float, float, str]] = [
    # ---------------- 삼성 ----------------
    ("삼성", "비스포크 무풍 갤러리 스탠드 17평형 (AF17BX738ESN)", 2050, 300, f"{_OFFICIAL} (삼성전자 제품 페이지)"),
    ("삼성", "무풍 갤러리 2in1 스탠드 17평형 (AF17CX738WSN)", 1900, 280, _PARTIAL),
    ("삼성", "비스포크 무풍 갤러리 스탠드 19평형 (AF19DX837VFRS)", 1950, 290, _PARTIAL),
    ("삼성", "무풍 슬림 스탠드 13평형", 1450, 230, _FAKE),
    ("삼성", "무풍 클래식 스탠드 15평형", 1650, 250, _FAKE),
    ("삼성", "무풍 클래식 스탠드 16평형", 1800, 270, _FAKE),
    ("삼성", "비스포크 무풍 클래식 스탠드 18평형", 2100, 310, _FAKE),
    ("삼성", "비스포크 AI 무풍 갤러리 스탠드 20평형", 2350, 330, _FAKE),
    ("삼성", "무풍 갤러리 스탠드 23평형", 2900, 400, _FAKE),
    ("삼성", "비스포크 무풍 스탠드 25평형", 3100, 430, _FAKE),
    # ---------------- LG ----------------
    ("LG", "휘센 오브제컬렉션 위너 스탠드 18평형 (FQ18HDWHY1)", 2200, 320, f"{_OFFICIAL} (LG전자 제품 페이지)"),
    ("LG", "휘센 오브제컬렉션 위너 스탠드 18평형 (FQ18HDWHA1M)", 2200, 320, f"{_OFFICIAL} (LG전자 제품 페이지)"),
    ("LG", "휘센 오브제컬렉션 타워 스탠드 18평형 (FQ18VCKBA1M)", 2250, 330, _PARTIAL),
    ("LG", "휘센 타워 스탠드 13평형", 1500, 240, _FAKE),
    ("LG", "휘센 듀얼 스탠드 15평형", 1750, 270, _FAKE),
    ("LG", "휘센 타워 스탠드 16평형", 1900, 290, _FAKE),
    ("LG", "휘센 오브제컬렉션 엣지 스탠드 17평형", 2100, 310, _FAKE),
    ("LG", "휘센 오브제컬렉션 타워 스탠드 20평형", 2450, 350, _FAKE),
    ("LG", "휘센 오브제컬렉션 뷰 스탠드 23평형", 2900, 410, _FAKE),
    ("LG", "휘센 오브제컬렉션 위너 스탠드 25평형", 3200, 440, _FAKE),
    # ---------------- 캐리어 ----------------
    ("캐리어", "에어로 18단 스탠드 18평형 (CPV-Q181ML)", 2050, 330, _PARTIAL + " (캐리어 판매처 사양표)"),
    ("캐리어", "스탠드 18평형 (CP-A185RHE)", 2190, 340, _PARTIAL + " (다나와 사양표)"),
    ("캐리어", "에어로 스탠드 13평형", 1500, 250, _FAKE),
    ("캐리어", "에어로 스탠드 15평형", 1700, 270, _FAKE),
    ("캐리어", "에어로 스탠드 16평형", 1850, 290, _FAKE),
    ("캐리어", "에어로 스탠드 17평형", 1950, 310, _FAKE),
    ("캐리어", "클라윈드 스탠드 18평형", 2150, 340, _FAKE),
    ("캐리어", "에어로 스탠드 20평형", 2400, 360, _FAKE),
    ("캐리어", "에어로 스탠드 23평형", 2850, 420, _FAKE),
    ("캐리어", "클라윈드 스탠드 25평형", 3150, 460, _FAKE),
]


class AirconDatabase:
    """에어컨 모델 DB (SQLite).

    with 문으로 사용하면 블록이 끝날 때 연결이 닫힌다.
    닫힌 뒤에 메서드를 부르면 sqlite3.ProgrammingError가 난다.
    """

    def __init__(self, path: Path | str = DB_PATH) -> None:
        """DB 파일을 열고(없으면 생성), 테이블과 시드 데이터를 준비한다.

        Args:
            path: SQLite 파일 경로. 기본값은 이 파일 옆의 aircon.db.
                ':memory:'를 주면 메모리 DB를 쓴다 (테스트용).

        Raises:
            sqlite3.Error: 파일을 열 수 없거나(권한·잠금 등) 스키마 생성에 실패할 때.
        """
        self.conn: sqlite3.Connection = sqlite3.connect(path)
        self._create_table()
        self._seed()

    def __enter__(self) -> "AirconDatabase":
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        """연결을 닫는다. 여러 번 불러도 안전하다."""
        self.conn.close()

    def _create_table(self) -> None:
        with self.conn:  # with 블록이 끝나면 자동 커밋
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS air_conditioners (
                    id       INTEGER PRIMARY KEY,
                    maker    TEXT NOT NULL,
                    name     TEXT NOT NULL,
                    rated    REAL NOT NULL CHECK (rated > 0),
                    maintain REAL NOT NULL CHECK (maintain > 0),
                    note     TEXT NOT NULL DEFAULT '',
                    UNIQUE (maker, name)
                )
            """)

    def _seed(self) -> None:
        # 이미 있는 모델(같은 제조사·모델명)은 건너뛰므로,
        # SEED_MODELS에 모델을 추가하면 다음 실행 때 기존 DB에도 반영된다.
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO air_conditioners (maker, name, rated, maintain, note) "
                "VALUES (?, ?, ?, ?, ?)",
                SEED_MODELS,
            )

    def makers(self) -> list[str]:
        """DB에 있는 제조사 목록을 처음 등록된 순서대로 돌려준다.

        Returns:
            중복 없는 제조사 이름 목록. DB가 비어 있으면 빈 리스트.
        """
        rows = self.conn.execute(
            "SELECT maker FROM air_conditioners GROUP BY maker ORDER BY MIN(id)"
        )
        return [row[0] for row in rows]

    def models_by_maker(self, maker: str) -> list[AirConditioner]:
        """해당 제조사의 모델을 등록 순서대로 돌려준다.

        Args:
            maker: 제조사 이름. 대소문자·공백까지 정확히 일치해야 한다.

        Returns:
            AirConditioner 목록. 해당 제조사가 없으면 빈 리스트 (예외 아님).

        Raises:
            ValueError: DB에 maintain > rated인 행이 있을 때
                (DB 파일을 직접 고쳐 규칙을 어긴 경우).
        """
        rows = self.conn.execute(
            "SELECT name, rated, maintain, maker, note FROM air_conditioners "
            "WHERE maker = ? ORDER BY id",
            (maker,),
        )
        return [AirConditioner(*row) for row in rows]

    def add(self, ac: AirConditioner) -> bool:
        """모델을 DB에 저장한다.

        Args:
            ac: 저장할 에어컨. (maker, name) 조합이 키로 쓰인다.

        Returns:
            저장했으면 True. 같은 제조사·모델명이 이미 있으면 False (DB는 그대로).

        Raises:
            sqlite3.Error: 중복 외의 DB 오류 (디스크 가득 참, 파일 잠김 등).
        """
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO air_conditioners (maker, name, rated, maintain, note) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (ac.maker, ac.name, ac.rated, ac.maintain, ac.note),
                )
        except sqlite3.IntegrityError:
            return False
        return True
