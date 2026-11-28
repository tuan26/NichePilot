# Quickstart – kiểm chứng E4 Bilingual Dashboard

Dữ liệu `MOCK`, không gọi API có phí, không mạng ngoài.

## 1. Kiểm thử tự động

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -m dashboard
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

## 2. Xem thử (development)

Chạy 3 lệnh seed demo E1, E2, E3 (xem `docs/operations/keywords.md` §4), đăng nhập → menu **Tổng quan** → bật MOCK → kiểm tra số liệu; mở
**Sản phẩm**, **Keyword**, **Agent Jobs**, **Chi phí**, **Cài đặt**; đổi EN, tải lại trang (vẫn EN); xuất CSV ở bảng xếp hạng ngách.

## 3. E2E

`E2E_SUITE=discovery` gồm test "E4 MOCK: tổng quan → sản phẩm → keyword → jobs → chi phí → cài đặt → EN".
