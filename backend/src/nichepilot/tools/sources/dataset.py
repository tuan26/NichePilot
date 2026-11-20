"""Adapter `open_dataset` / `licensed_data` – interface cho dữ liệu mở/được cấp phép (research R-13).

E1 chỉ định nghĩa interface: chưa có bộ dữ liệu cụ thể nào được xác minh, nên adapter thật trả UNAVAILABLE
(không tạo dữ liệu thay thế – FR-006a). Bản mock nằm ở `tools/mock_sources.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from nichepilot.tools.sources.base import PolicySnapshot, SourceResult


@dataclass
class DatasetAdapter:
    adapter_type: str = "open_dataset"
    data_origin: Literal["REAL", "MOCK"] = "REAL"

    async def query(
        self, policy: PolicySnapshot, query: str, *, market: str, language: str, max_results: int
    ) -> SourceResult:
        return SourceResult("UNAVAILABLE", reason="DATASET_ADAPTER_NOT_IMPLEMENTED")
