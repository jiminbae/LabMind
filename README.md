# LabMind

This README is available in [English](#english), [中文](#中文) and [한국어](#한국어).

## English

My part of LabMind provides the image-recognition backend and connects it to the Streamlit interface so a reagent-label image can be converted into structured OCR, inventory and expiry data.

### Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The app uses mock recognition by default. For live recognition, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, add the provider settings and API key, and set `LABMIND_VISION_MODE = "live"`. Never commit the secrets file.

### Current progress

- Backend OCR and structured-result pipeline completed
- Streamlit upload, preview, analysis and result display connected to the backend
- Partial OCR results, alternative candidates and error states supported
- Automated test suite passing; deployment configuration and CS B handoff guide included
- `site/` remains a static GitHub Pages demo and does not run the Python backend

See [CSB_INTEGRATION.md](CSB_INTEGRATION.md) for field mappings, deployment settings and verification steps.

---

## 中文

我负责的 LabMind 部分提供图像识别后端，并已连接到 Streamlit 界面，可将试剂标签图片转换为结构化的 OCR、库存和有效期数据。

### 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

应用默认使用模拟识别。若要启用真实识别，请将 `.streamlit/secrets.toml.example` 复制为 `.streamlit/secrets.toml`，填写服务商配置和 API 密钥，并设置 `LABMIND_VISION_MODE = "live"`。请勿提交密钥文件。

### 当前进度

- 后端 OCR 和结构化结果流程已完成
- Streamlit 的上传、预览、分析和结果展示已连接后端
- 已支持部分识别结果、候选结果和错误状态
- 自动测试已通过，并包含部署配置与 CS B 对接说明
- `site/` 仍是静态 GitHub Pages 演示版，不能运行 Python 后端

字段映射、部署设置和验证步骤见 [CSB_INTEGRATION.md](CSB_INTEGRATION.md)。

---

## 한국어

제가 담당한 LabMind 부분은 이미지 인식 백엔드를 제공하고 이를 Streamlit 인터페이스와 연결하여 시약 라벨 이미지를 구조화된 OCR, 재고 및 유효기간 데이터로 변환합니다.

### 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

앱은 기본적으로 모의 인식을 사용합니다. 실제 인식을 사용하려면 `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사하고 공급자 설정과 API 키를 입력한 뒤 `LABMIND_VISION_MODE = "live"`로 설정하세요. 비밀 설정 파일은 커밋하지 마세요.

### 현재 진행 상황

- 백엔드 OCR 및 구조화된 결과 파이프라인 완료
- Streamlit 업로드, 미리보기, 분석 및 결과 화면을 백엔드와 연결
- 부분 OCR 결과, 대체 후보 및 오류 상태 지원
- 자동 테스트 통과, 배포 설정 및 CS B 인수인계 문서 포함
- `site/`는 정적 GitHub Pages 데모이며 Python 백엔드를 실행하지 않음

필드 매핑, 배포 설정 및 검증 절차는 [CSB_INTEGRATION.md](CSB_INTEGRATION.md)를 참고하세요.
