# E1 T128 – trình duyệt cho profile tùy chọn browser-fetcher (TẮT mặc định, quyết định I1).
# Playwright server chính thức (Apache-2.0), cùng phiên bản với client Python (playwright==1.63.0 trong nhóm `browser`).
# KHÔNG cài plugin stealth/chống phát hiện; backend đặt User-Agent nhận diện được cho mỗi trang.
FROM mcr.microsoft.com/playwright:v1.63.0-noble
RUN useradd --system --create-home pwserver
USER pwserver
WORKDIR /home/pwserver
EXPOSE 3000
CMD ["npx", "-y", "playwright@1.63.0", "run-server", "--port", "3000", "--host", "0.0.0.0"]
