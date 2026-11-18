# DESIGN SPECIFICATION — BAL TECH COMMAND CENTER (`BAL TechRadar v2.0`)

- **Đơn vị chủ quản:** CÔNG TY TNHH THƯƠNG MẠI DỊCH VỤ VÀ SẢN XUẤT BẢO ANH LÂM (MST: `3401289271`)
- **Kiến trúc mục tiêu:** Next.js App Router (React + TypeScript) trên Vercel Cloud
- **Trạng thái cổng kiểm duyệt (`SDD Design Gate`):** **CHỜ GIÁM ĐỐC DUYỆT** — Tuyệt đối chưa sinh mã Frontend React/Next.js trước khi tài liệu này được xác nhận.
- **Chuẩn thẩm mỹ áp dụng:** `Emil Kowalski` + `Impeccable Design` + `Taste Skills` (Semantic Design Tokens `:root`, cấm giao diện AI đại trà tím/neon, không tràn ngang ở `320px`).

---

## 1. BẢNG MÀU CHUẨN (`Hex Color Palette & Semantic Tokens`)

Thiết kế theo phong cách **Executive Tactical Command Center** (nền tối sâu chống chói mắt khi đọc báo cáo tình báo công nghệ buổi sáng 05:00 AM, kết hợp màu nhận diện **Bảo Anh Lâm** Vàng Hoàng Gia & Xanh Ngọc Lục Bảo):

| Token CSS (`:root`) | Mã Hex | Vai trò sử dụng | Độ tương phản WCAG 2.2 |
| :--- | :--- | :--- | :--- |
| `--bg-canvas` | `#090D16` | Nền tổng thể Command Center & màn hình khóa PIN | Nền gốc |
| `--bg-surface` | `#111827` | Nền Panel chính (Danh sách Radar / Khung Chat AI) | Tách lớp rõ ràng trên `#090D16` |
| `--bg-surface-elevated` | `#172033` | Nền Card Repo nổi, Header cố định, Modal xác nhận | Nền nổi |
| `--bg-input` | `#0B1120` | Ô nhập Mã PIN, ô tìm kiếm Repo, ô gõ Chat với Gemini 4 | Nền chìm |
| `--brand-emerald` | `#1E5E3A` | Màu nhận diện gốc Bảo Anh Lâm (Badge hệ thống, trạng thái Đã tích hợp) | Với `#FFD800`: **7.1:1** (AAA) |
| `--brand-gold` | `#FFD800` | Điểm nhấn chỉ huy: Nút `[Duyệt & Triển Khai]`, số sao, huy hiệu Rank #1–#3 | Trên `#090D16`: **14.3:1** (AAA) |
| `--brand-gold-hover` | `#FFE44D` | Trạng thái Hover nút `[Duyệt & Triển Khai]` | **15.1:1** (AAA) |
| `--text-primary` | `#F8FAFC` | Tiêu đề Repo, nội dung tóm tắt tiếng Việt, tin nhắn AI | Trên `#111827`: **16.8:1** (AAA) |
| `--text-secondary` | `#CBD5E1` | Mô tả phụ, trích dẫn README | Trên `#111827`: **11.9:1** (AAA) |
| `--text-muted` | `#94A3B8` | Timestamp, metadata ngôn ngữ, số lượt fork | Trên `#111827`: **7.0:1** (AAA) |
| `--status-success` | `#10B981` | Kích hoạt Webhook GitHub Actions thành công / Đã xác thực PIN | Trên `#111827`: **7.8:1** (AAA) |
| `--status-warning` | `#F59E0B` | Đang chờ xử lý / Dry-run fallback | Trên `#111827`: **8.3:1** (AAA) |
| `--status-danger` | `#EF4444` | Sai mã PIN / Lỗi Webhook / Red Alert Bảo mật | Trên `#111827`: **4.9:1** (AA) |
| `--border-hairline` | `#1E293B` | Đường viền mảnh chia 2 luồng Split-Pane và viền Card | `1px solid` |
| `--border-focus` | `#FFD800` | Viền `:focus-visible` chuẩn trợ năng bàn phím | `2px solid` |

*Quy tắc chống Slop:* **Cấm 100%** dải màu gradient tím-hồng neon đại trà của AI; mọi thành phần bắt buộc dùng `var(--token)`, không hardcode màu trong component con.

---

## 2. CẤU TRÚC FONT CHỮ (`Typography System — Golden Ratio phi = 1.618`)

| Cấp độ chữ | Font Family | Cỡ chữ Compact Dashboard | `line-height` | `letter-spacing` & Thuộc tính |
| :--- | :--- | :--- | :--- | :--- |
| **Display / Lock Title** | `Space Grotesk`, `Montserrat`, `sans-serif` | `clamp(1.375rem, 2.2vw, 1.75rem)` | `1.15` | `-0.025em`, `font-weight: 800`, `text-wrap: balance` |
| **Section Heading (`h2`)** | `Space Grotesk`, `Montserrat`, `sans-serif` | `clamp(1rem, 1.35vw, 1.15rem)` | `1.20` | `-0.02em`, `font-weight: 700`, `text-wrap: balance` |
| **Repo Title (`h3`)** | `Inter`, `system-ui`, `sans-serif` | `0.90625rem` (`14.5px`) | `1.30` | `-0.01em`, `font-weight: 700` |
| **Body / Summary VI / Chat** | `Inter`, `system-ui`, `sans-serif` | `0.8125rem` (`13px`) | `1.52` | `0em`, `max-width: 68ch`, `text-wrap: pretty` |
| **Badge / JSON / PIN / Metrics / Fit Score** | `JetBrains Mono`, `ui-monospace`, `monospace` | `0.71875rem` (`11.5px`) | `1.40` | `font-variant-numeric: tabular-nums` (thẳng hàng điểm F&B/Xe & số sao) |

---

## 3. HỆ THỐNG LƯỚI & KHOẢNG CÁCH (`Layout Grid & Spacing Rhythm 4px / 8px`)

### 3.1. Nhịp khoảng cách gốc (Base Unit = `4px` / `0.25rem`)
- `--space-1`: `4px` (`0.25rem`) — khoảng cách icon và nhãn
- `--space-2`: `8px` (`0.5rem`) — gap giữa các tag/badge
- `--space-3`: `12px` (`0.75rem`) — padding nút bấm
- `--space-4`: `16px` (`1rem`) — padding card nội bộ & gap lưới tiêu chuẩn
- `--space-6`: `24px` (`1.5rem`) — khoảng cách giữa các cụm panel chính

### 3.2. Bố cục Chia 2 Luồng (`Split-Pane Command Architecture`)
1. **Desktop & Laptop (`>= 1024px`):**
   - Header thanh chỉ huy cố định (`height: 64px`, `border-bottom: 1px solid var(--border-hairline)`): Logo Bảo Anh Lâm, bộ lọc ngôn ngữ (`Tất cả 30` / `Python (15)` / `TypeScript (15)`), chế độ xem (`Thẻ trực quan` | `JSON thô`), và nút `[🔒 Khóa phiên]`.
   - Khung nội dung cao `calc(100dvh - 64px)`, chia lưới 2 cột theo **Tỷ lệ vàng**:
     - **Luồng Trái (`61.8%` / `minmax(0, 1.618fr)`):** Danh sách **30 Repository GitHub Radar** cuộn độc lập, hiển thị Badge `#rank`, ngôn ngữ, ⭐ sao (`tabular-nums`), tóm tắt tiếng Việt (`<= 3 câu`), khối JSON inspector đóng/mở được, và nút **`[⚡ Duyệt & Triển Khai]`** (`min-height: 44px`).
     - **Luồng Phải (`38.2%` / `minmax(360px, 1fr)`):** **Khung Chatbox AI (`Gemini 4 Argon`)** cố định toàn chiều cao bên phải, tự động nạp ngữ cảnh repo đang chọn để Giám đốc hỏi sâu kiến trúc hoặc yêu cầu phân tích tích hợp vào Hy Chay / BAL System.
2. **Tablet (`768px – 1023px`):**
   - Chia `55% / 45%` hoặc xếp dọc có thanh chuyển nhanh.
3. **Mobile (`320px – 767px`):**
   - Thanh chuyển Tab ghim trên cùng (`[📡 Radar 30 Repo]` | `[🤖 Chat Gemini 4]`), mỗi panel chiếm `100%` chiều rộng, tuyệt đối **0px tràn ngang ở `320px`**, mọi nút bấm và input đạt kích thước chạm tối thiểu **`44px x 44px`**.

---

## 4. THÔNG SỐ BO GÓC (`Concentric Border Radius System`)

Áp dụng nghiêm ngặt công thức bo góc đồng tâm (`outer_radius = inner_radius + inner_padding`):

| Thành phần UI | Thông số `border-radius` | Quy tắc đồng tâm |
| :--- | :--- | :--- |
| **Màn hình khóa PIN Card / Drawer Deploy** | `20px` (`--radius-xl`) | Khung ngoài lớn nhất |
| **Card Repository / Khung Chat Panel** | `16px` (`--radius-lg`) | Lớp chứa danh sách & bong bóng chat |
| **Ô nhập Mã PIN / Input Chat / Khối Code JSON** | `12px` (`--radius-md`) | Lồng trong Card (`padding: 16px` / `8px`) |
| **Nút `[Duyệt & Triển Khai]`, Nút Gửi Chat, Nút Lọc** | `8px` (`--radius-sm`) | Nằm trong container `16px` + `padding: 8px` |
| **Huy hiệu Ngôn ngữ / Status Pill (`Python`, `TS`)** | `9999px` (`--radius-pill`) | Bo tròn viên thuốc nhỏ gọn |

---

## 5. HIỆU ỨNG CHUYỂN ĐỘNG (`Emil Kowalski Physics & GPU-Only Motion`)

1. **Nguyên tắc Compositor Bắt buộc:** Chỉ animate **`transform`** và **`opacity`**. Nghiêm cấm animate `width`, `height`, `top`, `left` để đảm bảo `60fps` trên máy 8GB RAM.
2. **Đường cong & Thời lượng chuẩn hóa:**
   - **Mở khóa PIN Overlay (`Unlock Transition`) & Modal Xác nhận Triển Khai:**
     - Curve: `cubic-bezier(0.22, 1, 0.36, 1)`
     - Duration: `220ms` (`opacity: 0 -> 1`, `transform: translateY(10px) scale(0.98) -> translateY(0) scale(1)`)
   - **Chuyển Tab Mobile / Mở Inspector JSON / Tin nhắn Chat mới xuất hiện:**
     - Curve: `cubic-bezier(0.32, 0.72, 0, 1)`
     - Duration: `200ms`
   - **Phản hồi nhấn vật lý (Tactile Press Feedback trên nút `[Duyệt & Triển Khai]` & bàn phím PIN):**
     - `:active` -> `transform: scale(0.97)` trong `120ms`
   - **Rung nhẹ khi nhập sai PIN (PIN Error Shake):**
     - `@keyframes bal-pin-shake` chỉ dịch chuyển `transform: translateX(-6px <-> +6px)` trong `240ms`.
3. **Tôn trọng Hệ điều hành:**
   - Bắt buộc khai báo `@media (prefers-reduced-motion: reduce)` vô hiệu hóa toàn bộ transition/animation cho người dùng nhạy cảm chuyển động.

---

## 6. RÀNG BUỘC BẢO MẬT & TÍCH HỢP VERCEL (`API Shield Ready`)
- **Màn hình Khóa PIN Nội bộ:** Xác thực qua Serverless API `/api/auth` đối chiếu `process.env.BAL_COMMAND_PIN` (tuyệt đối không lộ PIN trong bundle React phía trình duyệt), cấp session cookie `HttpOnly; SameSite=Strict`.
- **Bộ Chuyển Mạch AI Model Switcher & Chatbox (`/api/chat`):** Hỗ trợ chuyển đổi tức thì giữa `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.5-flash-lite` và `claude-3-5-sonnet` qua biến môi trường `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`.
- **Tiêu chí Đánh giá Thực chiến F&B (`Hy Chay`) & Xe Dịch Vụ (`Đình Nhân Car`):** Tự động chấm điểm `BAL Fit (0-100)`, phân loại ngành (`F&B`, `Xe Dịch Vụ`, `Hạ tầng Chung`), mức độ tối ưu `RAM 8GB`, và đề xuất kịch bản tích hợp trên từng thẻ repo.
- **Lệnh `[Duyệt & Triển Khai]`:** Gọi `/api/deploy` -> gửi `POST` tới GitHub Actions `workflow_dispatch` / `repository_dispatch` bằng `process.env.GITHUB_DISPATCH_TOKEN` phía máy chủ Vercel, truyền kèm `repo_full_name`, `repo_url`, `target_company_repo` để Antigravity tự động tải mã nguồn, viết file tích hợp biến môi trường và push code.
