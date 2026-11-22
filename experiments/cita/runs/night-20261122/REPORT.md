# Thực nghiệm qua đêm

Cập nhật 2026-11-22T02:55:09+07:00. Hạn dừng 2026-11-22T09:13:18+07:00.
Trạng thái: queue_complete. Đã ghi 1268 tác vụ.

| Nhánh | Hoàn tất | Hết giờ | Giới hạn tài nguyên | Lỗi / khác |
|---|---:|---:|---:|---:|
| anchor | 300 | 0 | 0 | 0 |
| index | 3 | 0 | 306 | 0 |
| certificate | 100 | 0 | 0 | 0 |
| batch | 250 | 0 | 0 | 0 |
| budget | 84 | 0 | 61 | 0 |
| policy | 164 | 0 | 0 | 0 |

## So sánh ghép cặp

Hệ số là trung vị thời gian phương án đầu chia phương án sau, trên các ca cả hai hoàn tất. Tỷ lệ hoàn tất và giới hạn tài nguyên phải được đọc cùng thời gian. Peak RSS là tổng RSS lấy mẫu của worker và tiến trình con, có thể tính trùng trang dùng chung.

- anchor, baseline / three: 100 cặp; thời gian 3.13×, RSS 1.73×.
- anchor, baseline / two: 100 cặp; thời gian 1.89×, RSS 1.15×.
- index, dense / rank: 1 cặp; thời gian 0.96×, RSS 0.99×.
- index, hash / rank: 1 cặp; thời gian 1.44×, RSS 1.02×.
- batch, cold / hash: 125 cặp; thời gian 1.56×, RSS 0.98×.

- Với nghiệm heuristic thực sự tìm được: 16/100 ca chứng nhận tối ưu tiếp tiết kiệm tối đa 1%; ở mức 2% là 36/100.

## Giới hạn mở rộng

- budget, n=16, k=4, B=2: 1/1 lượt hoàn tất.
- budget, n=16, k=4, B=4: 1/1 lượt hoàn tất.
- budget, n=16, k=4, B=6: 1/1 lượt hoàn tất.
- budget, n=16, k=4, B=8: 1/1 lượt hoàn tất.
- budget, n=18, k=6, B=2: 1/1 lượt hoàn tất.
- budget, n=18, k=6, B=4: 1/1 lượt hoàn tất.
- budget, n=18, k=6, B=6: 1/1 lượt hoàn tất.
- budget, n=18, k=6, B=8: 1/1 lượt hoàn tất.
- budget, n=20, k=4, B=2: 3/3 lượt hoàn tất.
- budget, n=20, k=4, B=4: 3/3 lượt hoàn tất.
- budget, n=20, k=4, B=6: 0/3 lượt hoàn tất.
- budget, n=20, k=4, B=8: 0/3 lượt hoàn tất.
- budget, n=20, k=8, B=2: 1/1 lượt hoàn tất.
- budget, n=20, k=8, B=4: 1/1 lượt hoàn tất.
- budget, n=20, k=8, B=6: 1/1 lượt hoàn tất.
- budget, n=20, k=8, B=8: 1/1 lượt hoàn tất.
- budget, n=24, k=6, B=2: 0/3 lượt hoàn tất.
- budget, n=24, k=6, B=4: 0/3 lượt hoàn tất.
- budget, n=24, k=6, B=6: 0/3 lượt hoàn tất.
- budget, n=24, k=6, B=8: 0/3 lượt hoàn tất.
- budget, n=24, k=8, B=2: 33/33 lượt hoàn tất.
- budget, n=24, k=8, B=4: 33/33 lượt hoàn tất.
- budget, n=24, k=8, B=6: 0/23 lượt hoàn tất.
- budget, n=24, k=8, B=8: 0/20 lượt hoàn tất.
- index, n=12, k=4, B=4: 3/3 lượt hoàn tất.
- index, n=24, k=6, B=4: 0/105 lượt hoàn tất.
- index, n=26, k=6, B=4: 0/99 lượt hoàn tất.
- index, n=28, k=6, B=4: 0/102 lượt hoàn tất.

## Quyết định cấu hình trước khi biết nhu cầu

- Depot 0, n=16: mean chọn 0-0-1-3, regret kiểm tra TB 0.27%, tệ nhất 1.72%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.27%, tệ nhất 1.72%.
- Depot 0, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.00%, tệ nhất 0.00%, minimax chọn 0-0-0-4, regret kiểm tra TB 1.47%, tệ nhất 5.26%.
- Depot 1, n=16: mean chọn 0-0-1-3, regret kiểm tra TB 0.16%, tệ nhất 0.74%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.16%, tệ nhất 0.74%.
- Depot 1, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.16%, tệ nhất 0.65%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.16%, tệ nhất 0.65%.
- Depot 2, n=16: mean chọn 0-0-1-3, regret kiểm tra TB 0.64%, tệ nhất 2.52%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.64%, tệ nhất 2.52%.
- Depot 2, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 1.61%, tệ nhất 2.61%, minimax chọn 0-0-1-3, regret kiểm tra TB 1.61%, tệ nhất 2.61%.
- Depot 3, n=16: mean chọn 0-0-1-3, regret kiểm tra TB 1.18%, tệ nhất 4.10%, minimax chọn 0-0-1-3, regret kiểm tra TB 1.18%, tệ nhất 4.10%.
- Depot 3, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.00%, tệ nhất 0.00%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.00%, tệ nhất 0.00%.
- Depot 4, n=20: mean chọn 0-0-0-4, regret kiểm tra TB 0.44%, tệ nhất 1.90%, minimax chọn 0-0-0-4, regret kiểm tra TB 0.44%, tệ nhất 1.90%.
- Depot 5, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.17%, tệ nhất 0.39%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.17%, tệ nhất 0.39%.
- Depot 6, n=20: mean chọn 0-0-0-4, regret kiểm tra TB 0.20%, tệ nhất 0.45%, minimax chọn 0-0-0-4, regret kiểm tra TB 0.20%, tệ nhất 0.45%.
- Depot 7, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.22%, tệ nhất 1.11%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.22%, tệ nhất 1.11%.
- Depot 8, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.53%, tệ nhất 1.61%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.53%, tệ nhất 1.61%.
- Depot 9, n=20: mean chọn 0-0-1-3, regret kiểm tra TB 0.37%, tệ nhất 1.16%, minimax chọn 0-0-1-3, regret kiểm tra TB 0.37%, tệ nhất 1.16%.
