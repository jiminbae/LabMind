# LabMind — CSA CAS & Database Backend

> This branch README is available in [English](#english), [中文](#中文), and [한국어](#한국어).

## English

### Branch purpose

`feature/csa-cas-database` adds the CS A database foundation to CS B's
Streamlit frontend base. The existing `app.py`, `app_v5.py`, and `site/`
interface remain unchanged so the backend contract can be reviewed before UI
integration.

### Completed

- Strict CAS format and check-digit validation
- SQLite schema for reagent lots and reviewed storage suggestions
- Repeatable database initialization with stable project paths
- Human-confirmed reagent insertion
- CAS-based lookup that supports multiple lots
- Newest-first inventory listing
- Validation for quantities, dates, and JSON list fields
- 22 focused backend tests passing

CAS check-digit validation catches formatting and digit errors. It does not
prove that the CAS number belongs to the chemical shown on a label.

### Run

Install the project dependencies:

```powershell
pip install -r requirements.txt
```

Initialize the local development database:

```powershell
python -m backend.db_init
```

Run the CSA backend tests:

```powershell
python -m unittest tests.test_cas_validator tests.test_db_init tests.test_db_utils -v
```

Run the existing Streamlit interface:

```powershell
streamlit run app.py
```

### Integration status

The frontend is not connected to these database functions yet. The intended
interfaces are:

```python
from backend.db_utils import insert_reagent, list_reagents, query_by_cas
```

CS B can use the field mapping and integration notes in
[`CSA_BACKEND_HANDOFF.md`](CSA_BACKEND_HANDOFF.md) when replacing the current
sample registration and inventory data.

The revised MVP does not persist `pending_order`. `inventory.db` is ignored by
Git and is suitable only for local development; public deployment still needs
a persistent hosted database.

### Next step

Connect the reviewed registration payload in `app_v5.py` to
`insert_reagent(..., confirmed=True)`, then replace the sample inventory
DataFrame with `query_by_cas` and `list_reagents`. The frontend test that
currently forbids backend imports must be updated during that integration.

---

## 中文

### 分支用途

`feature/csa-cas-database` 在 CS B 的 Streamlit 前端基础上加入 CS A 的数据库后端。
现有的 `app.py`、`app_v5.py` 和 `site/` 界面保持不变，以便队友先审核后端接口，
再进行前后端连接。

### 已完成

- 严格的 CAS 格式和校验位检查
- 用于试剂批次及人工审核存储建议的 SQLite Schema
- 使用稳定项目路径、可重复运行的数据库初始化
- 必须经人工确认的试剂入库
- 支持同一 CAS 多个批次的查询
- 按最新记录优先显示的库存列表
- 对数量、日期和 JSON 列表字段的输入校验
- 22项后端专项测试全部通过

CAS 校验位可以发现格式和数字错误，但不能证明该 CAS 号一定属于标签上的化学品。

### 运行方式

安装项目依赖：

```powershell
pip install -r requirements.txt
```

初始化本地开发数据库：

```powershell
python -m backend.db_init
```

运行 CS A 后端测试：

```powershell
python -m unittest tests.test_cas_validator tests.test_db_init tests.test_db_utils -v
```

运行现有 Streamlit 界面：

```powershell
streamlit run app.py
```

### 集成状态

前端目前还没有连接这些数据库函数。计划使用的接口为：

```python
from backend.db_utils import insert_reagent, list_reagents, query_by_cas
```

CS B 可以参考 [`CSA_BACKEND_HANDOFF.md`](CSA_BACKEND_HANDOFF.md) 中的字段对应关系，
替换当前的示例登记和库存数据。

新版 MVP 不保存 `pending_order`。`inventory.db` 已被 Git 忽略，只适合本地开发；
公开部署仍然需要可持久保存的托管数据库。

### 下一步

把 `app_v5.py` 中经过人工确认的登记数据连接到
`insert_reagent(..., confirmed=True)`，然后使用 `query_by_cas` 和
`list_reagents` 替换示例库存 DataFrame。前端中目前禁止导入后端模块的测试，
也需要在集成时同步更新。

---

## 한국어

### 브랜치 목적

`feature/csa-cas-database` 브랜치는 CS B의 Streamlit 프런트엔드 기반에
CS A의 데이터베이스 백엔드를 추가합니다. 백엔드 계약을 먼저 검토한 후 UI를
연결할 수 있도록 기존 `app.py`, `app_v5.py`, `site/` 인터페이스는 변경하지
않았습니다.

### 완료된 작업

- 엄격한 CAS 형식 및 검사 숫자 검증
- 시약 로트와 검토된 보관 위치 제안을 위한 SQLite 스키마
- 안정적인 프로젝트 경로를 사용하는 반복 실행 가능한 데이터베이스 초기화
- 사용자 확인 후 시약 등록
- 동일한 CAS의 여러 로트를 지원하는 조회
- 최신 항목 우선 재고 목록
- 수량, 날짜, JSON 목록 필드 검증
- 백엔드 집중 테스트 22개 통과

CAS 검사 숫자 검증은 형식 및 숫자 오류를 찾을 수 있지만, 해당 CAS 번호가
라벨의 화학물질과 실제로 일치함을 증명하지는 않습니다.

### 실행 방법

프로젝트 의존성을 설치합니다:

```powershell
pip install -r requirements.txt
```

로컬 개발 데이터베이스를 초기화합니다:

```powershell
python -m backend.db_init
```

CS A 백엔드 테스트를 실행합니다:

```powershell
python -m unittest tests.test_cas_validator tests.test_db_init tests.test_db_utils -v
```

기존 Streamlit 인터페이스를 실행합니다:

```powershell
streamlit run app.py
```

### 통합 상태

프런트엔드는 아직 새 데이터베이스 함수에 연결되지 않았습니다. 사용할 인터페이스는
다음과 같습니다:

```python
from backend.db_utils import insert_reagent, list_reagents, query_by_cas
```

CS B는 [`CSA_BACKEND_HANDOFF.md`](CSA_BACKEND_HANDOFF.md)의 필드 매핑과 통합
설명을 사용해 현재 샘플 등록 및 재고 데이터를 교체할 수 있습니다.

개정된 MVP는 `pending_order`를 저장하지 않습니다. `inventory.db`는 Git에서
제외되며 로컬 개발에만 적합합니다. 공개 배포에는 영구 저장이 가능한 호스팅
데이터베이스가 필요합니다.

### 다음 단계

`app_v5.py`에서 검토가 완료된 등록 데이터를
`insert_reagent(..., confirmed=True)`에 연결한 후, 샘플 재고 DataFrame을
`query_by_cas`와 `list_reagents`로 교체합니다. 현재 백엔드 모듈 가져오기를
금지하는 프런트엔드 테스트도 통합 과정에서 함께 수정해야 합니다.
