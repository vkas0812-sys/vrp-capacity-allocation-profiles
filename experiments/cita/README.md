# Thực nghiệm CVRP cho CITA 2027

## Câu hỏi và thiết kế

- RQ1. Điều kiện tải chặt giúp giảm bao nhiêu chi phí sinh và định giá tuyến? Trên từng instance gốc, so sánh lọc theo `load == Q` với chỉ lọc theo `load <= Q`. Cả hai dùng cùng cách định giá Held–Karp, cùng cận tải tại bước ghép tuyến và cùng cách đếm phân hoạch. Phép so sánh này cô lập tác động của việc áp dụng cận dưới **trước** khi định giá tuyến.
- RQ2. Tăng nhẹ sức chứa mỗi xe ảnh hưởng thế nào đến số tuyến ứng viên, số phân hoạch, thời gian giải và chi phí tối ưu? Giữ nguyên tọa độ, nhu cầu và bốn xe sử dụng. Với mỗi instance, thử `Q`, `Q+1` và `Q+ceil(p*Q/100)` cho `p=2,5,10`. Các biến thể được tạo từ dữ liệu gốc và giữ cố định các yếu tố khác.
- Đầu vào gồm 55 file CVRP `XSH-n20-k4`, mỗi instance có 20 khách hàng, bốn xe, một depot, nhu cầu nguyên dương và khoảng cách `EUC_2D` làm tròn theo TSPLIB. Các file trong bộ này dùng các mục tọa độ, nhu cầu và depot. Dòng `Optimal cost` chỉ dùng khi đối chiếu kết quả. [QOBLIB 09-routing tại commit đã dùng](https://github.com/ZIB-AOPT/QOBLIB/tree/55384509a610f040bea517a6c16079ce5c4edf0d/09-routing/instances)

## Phương pháp và kiểm chứng

1. Với tổng nhu cầu `D`, sức chứa `C` và bốn tuyến không rỗng, mỗi tuyến có tải ít nhất `max(1, D-3C)`, vì ba tuyến còn lại gánh tối đa `3C`. Đặt độ dư tải `Δ=4C-D`, ta có khoảng tải `[max(1,C-Δ), C]`. Khi `Δ=0`, từng tuyến phải có tải đúng `C`.
2. Liệt kê các tập khách hàng có tải trong khoảng này. Held–Karp tính chi phí tour khép kín nhỏ nhất cho từng tập. Sau đó tìm các exact cover bằng bốn tập rời nhau. Mỗi tuyến tiếp theo chứa khách hàng có chỉ số nhỏ nhất chưa được phủ, nên mỗi phân hoạch không thứ tự được đếm một lần. Bộ giải lưu số cách chia cho hai tuyến cuối theo tập khách hàng còn lại. Chi phí của một phân hoạch là tổng các tour tối ưu của bốn tập. `optimal_partitions` đếm số phân hoạch đồng hạng, còn `second_distinct_objective` là chi phí phân hoạch nhỏ nhất lớn hơn tối ưu. [Held và Karp](https://doi.org/10.1137/0110015)
3. Trên dữ liệu gốc, SciPy/HiGHS giải một MILP set partitioning có một biến nhị phân cho mỗi tuyến ứng viên, mỗi khách hàng xuất hiện đúng một lần và chọn đúng bốn tuyến. Đối chiếu cả mục tiêu lẫn cận dưới với exact cover. MILP dùng chung danh sách tập và chi phí Held–Karp, nên đây là kiểm chứng độc lập bước **chọn tuyến**. Các dòng tải dư dùng exact cover. [Balinski và Quandt](https://doi.org/10.1287/opre.12.2.300) · [SciPy MILP](https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.optimize.milp.html)
4. Một phép quy hoạch động bằng Python dựng lại tour cho các tập được chọn rồi đối chiếu độ phủ, tải và chi phí. Checker Rust chính thức kiểm tra các tuyến đã xuất. Tool này có thể chấp nhận tuyến hợp lệ dù chi phí khai báo lệch, nên runner kiểm tra thêm dòng tổng chi phí và các cảnh báo. Với dữ liệu tải dư, checker đọc bản sao file gốc với sức chứa mới. Mục tiêu tối ưu được xác định bằng phân hoạch toàn bộ ứng viên và đối chiếu MILP trên 55 bản gốc. [Checker QOBLIB](https://github.com/ZIB-AOPT/QOBLIB/tree/55384509a610f040bea517a6c16079ce5c4edf0d/09-routing/check)

## Chạy lại

Yêu cầu Python 3.11, Clang có C++17, và Cargo để chạy checker. Các lệnh dưới chạy từ thư mục gốc repo. Đường dẫn kết quả nằm ngoài repo để tiện so sánh với lần chạy đã lưu.

```sh
WORK=$(mktemp -d)
R=experiments/cita
python3.11 -m venv "$WORK/venv"
PY="$WORK/venv/bin/python"
"$PY" -m pip install -r "$R/requirements.txt"
mkdir -p "$WORK/check/src/bin" "$WORK/results"

QOBLIB=https://raw.githubusercontent.com/ZIB-AOPT/QOBLIB/55384509a610f040bea517a6c16079ce5c4edf0d/09-routing/check
for f in Cargo.toml Cargo.lock src/bin/check_cvrp.rs; do
  curl -fsSL "$QOBLIB/$f" -o "$WORK/check/$f"
done
cargo build --release --locked --manifest-path "$WORK/check/Cargo.toml"
CHECKER="$WORK/check/target/release/check_cvrp"

TC=https://raw.githubusercontent.com/vkas0812-sys/qoblib-routing-exact-sqa/675fbfc/src/qoblib_routing_experiments.cpp
curl -fsSL "$TC" -o "$WORK/tc-qoblib_routing_experiments.cpp"
clang++ -std=c++17 -O3 -I"$WORK" "$R/replay_tc_exact.cpp" -o "$WORK/replay"
clang++ -std=c++17 -O3 -Wall -Wextra -pedantic "$R/exact.cpp" -o "$WORK/exact"
"$PY" "$R/benchmark.py" --download --instances "$WORK/instances" \
  --output "$WORK/results" --binary "$WORK/exact" --checker "$CHECKER" \
  --repeats 5 --stress-repeats 2 --time-limit 10
"$WORK/replay" "$WORK/instances" > "$WORK/results/tc_exact_replay.csv"
MPLCONFIGDIR="$WORK/matplotlib" "$PY" "$R/report.py" \
  --results "$WORK/results" --instances "$WORK/instances" --checker "$CHECKER"
```

- SHA-256 mã TC-Exact đã chạy: `a2a5b20b382cb3cf1c046c8b2cbb74f62246346e770116301dd4a913653e20d8`.
- SHA-256 mã nguồn checker: `b4e39b0e4d1f15e1acdddbacb06bf456c10127aa7a6522108e98f003c0b9333a`.
- [Metadata và hash của 55 input](results/metadata.json), [lần chạy TC-Exact gốc](results/tc_exact_replay.csv), [số liệu từng trường hợp](results/per_instance.csv), [thời gian từng lượt](results/repetitions.csv), [tuyến và chi phí](results/solutions.json), [kết quả kiểm tra tuyến](results/solution_verification.json).

## Sử dụng khi viết

### Kết quả đã kiểm chứng

TC-Exact gốc, bộ giải exact cover và cận tối ưu HiGHS khớp trên **55/55 instance gốc**. Checker Rust chấp nhận **275/275 bộ tuyến** và xác nhận lại đúng chi phí ở năm mức sức chứa. Ở tải gốc, sinh tuyến theo cận tải chặt giảm số ứng viên **51,44 lần** và thời gian định giá tuyến **25,72 lần**, theo trung vị tỷ số ghép cặp.

| Sức chứa mỗi xe | Trung vị số phân hoạch | Trung vị hệ số tăng so với bản gốc, ghép cặp | Trung vị thời gian exact (ms) | Trung vị mức giảm chi phí tối ưu, ghép cặp |
|---|---:|---:|---:|---:|
| Gốc | 2.334 | 1,0× | 1,74 | 0% |
| +1 đơn vị | 88.338 | 39,9× | 9,40 | 10,79% |
| +2% | 5.237.545 | 2.147× | 66,43 | 15,64% |
| +5% | 63.376.232 | 25.045× | 175,62 | 16,96% |
| +10% | 427.619.367 | 173.404× | 417,97 | 18,92% |

### Diễn giải

- Dùng [bảng theo mức sức chứa](results/scenario_summary.csv), [so sánh lọc tải ở dữ liệu gốc](results/pricing_ablation.json) và [hình tổng hợp](results/capacity_sensitivity.png) cho phần kết quả. Biểu đồ thể hiện trung vị và khoảng tứ phân vị trên 55 instance. Tỷ số ghép cặp được tính từng instance trước rồi lấy trung vị.
- Thời gian exact gồm sinh và định giá tuyến, rồi tìm phân hoạch. Loại thời gian đọc file, khởi động tiến trình, kiểm tra tuyến và MILP. Mỗi cấu hình ở tải gốc chạy năm lượt, mỗi cấu hình tải dư hai lượt. MILP chạy một lượt trên mỗi bản gốc, tính từ khi dựng mô hình cho đến khi trả kết quả. Không diễn giải hai cột thời gian như so sánh hiệu năng đầu-cuối giữa các solver.
- Giới hạn suy rộng nằm ở bộ QOBLIB XSH, 20 khách hàng, bốn xe và biến thể sức chứa có kiểm soát. Số lượng phân hoạch không thứ tự là số cách chia **tập khách hàng**, khác với số thứ tự ghé thăm khả dĩ trong tuyến. Chi phí thấp hơn khi nới tải là thay đổi nghiệm của bài toán với sức chứa mới.
- Dùng TC-Exact gốc và mốc 842 làm kết quả tái lập. Mốc 842 đã có trong header của file `-21` ở commit QOBLIB dùng tại đây. Phần mới để đối chiếu với technical note gồm thí nghiệm tải dư ghép cặp, phép đo tác động của lọc tải trước khi định giá và kiểm chứng cận bằng MILP. [Technical note cùng tác giả](https://github.com/vkas0812-sys/qoblib-routing-exact-sqa/blob/675fbfc/paper/main.tex) · [PR TC-Exact](https://github.com/ZIB-AOPT/QOBLIB/pull/93)
- Khi viết bản nộp, trích technical note và nêu phần thực nghiệm mở rộng, đối chiếu tình trạng xuất bản của note với quy định originality của CITA. Các ghi chú trong thư mục này phục vụ chạy lại thí nghiệm và đọc số liệu; tác giả tự viết bản nộp theo yêu cầu của CFP về văn bản do LLM tạo. [CFP CITA 2027](https://cita-conf.org/)

## Kiểm chứng bổ sung ở tải dư

Chạy hai lệnh dưới sau bước benchmark ở trên, từ thư mục gốc với cùng biến môi trường. Script đọc chi phí tham chiếu và số phân hoạch từ bảng kết quả trong repo. Thư mục kết quả nhận các bảng mới.

```sh
"$PY" "$R/robustness.py" ablation --instances "$WORK/instances" --binary "$WORK/exact"
"$PY" "$R/robustness.py" arc --instances "$WORK/instances" --seconds 10
```

- **Ablation ghép cặp.** Trên 55 instance ở mức +1 đơn vị, +2% và +5%, cả hai chế độ dùng cùng bước ghép tuyến. Chế độ bounded áp dụng cận dưới ngay khi sinh các tập cần định giá. Chế độ capacity_only định giá mọi tập không rỗng vừa sức chứa. Mỗi chế độ chạy ba lượt liên tiếp, thứ tự hai chế độ luân phiên theo instance và kịch bản. Hệ số tăng tốc là thời gian capacity_only chia cho bounded, lấy trung vị từng chế độ trước khi chia, rồi lấy trung vị trên 55 instance. Kiểm tra số phân hoạch, số phân hoạch tối ưu, chi phí tối ưu và chi phí phân hoạch phân biệt kế tiếp ở từng cặp. [Số liệu từng lượt](results/slack_ablation.csv) · [Tóm tắt theo kịch bản](results/slack_ablation_summary.csv)
- **MILP theo cạnh.** Trên chín instance chọn đều theo thứ hạng tăng số phân hoạch ở mức +1, giải lại kịch bản +5% với ngân sách mục tiêu 10 giây mỗi instance. Mô hình xây từ khoảng cách và nhu cầu, dùng bậc 2 ở khách hàng và bậc 8 ở depot. Các cạnh depot cho phép hệ số 2 để mô tả tuyến một khách. Với mỗi thành phần khách hàng vi phạm, thêm bất đẳng thức tổng số cạnh đi qua biên ít nhất bằng hai lần số xe tối thiểu cần để phục vụ thành phần. Mỗi vòng là một MILP thư giãn, nên cận dưới vẫn có giá trị khi hết giờ. Một nghiệm nguyên có đủ bốn tuyến kết nối depot và tuân thủ tải là nghiệm khả thi. Cột certified kiểm tra cận dưới nguyên của MILP có khớp chi phí của bộ giải exact hay không. Cột bound_gap_pct dùng chi phí exact làm mẫu số. [Kết quả kiểm chứng độc lập](results/arc_baseline.csv)

Đặt kết quả cạnh nghiên cứu *Constrained Fitness Landscape Analysis of Capacitated Vehicle Routing Problems*, vốn cũng thay đổi sức chứa khi giữ cố định số xe. Câu hỏi cụ thể ở đây là việc áp dụng sớm cận dưới tải tiết kiệm bao nhiêu lần định giá tuyến, và phần tiết kiệm này chiếm bao nhiêu trong tổng thời gian tìm nghiệm exact ở từng mức tải dư của XSH. [Bài nghiên cứu đối chiếu](https://pmc.ncbi.nlm.nih.gov/articles/PMC8775137/)

| Sức chứa | Số tập phải định giá giảm theo hệ số | Tăng tốc định giá | Tăng tốc toàn bộ bộ giải | Khoảng tứ phân vị của tăng tốc toàn bộ | Instance nhanh hơn |
|---|---:|---:|---:|---:|---:|
| +1 đơn vị mỗi xe | 10,49× | 6,21× | 4,45× | 4,02–4,73× | 55/55 |
| +2% | 2,76× | 1,92× | 1,34× | 1,24–1,43× | 52/55 |
| +5% | 1,51× | 1,22× | 1,04× | 0,99–1,14× | 38/55 |

Các hệ số ở bảng là trung vị ghép cặp. Tất cả 165 cặp đều khớp bốn đại lượng kiểm tra. Ở +5%, khoảng tứ phân vị của thời gian có chứa mốc 1×, nên mức cải thiện toàn bộ nhỏ và thay đổi theo instance. Số lượng ứng viên và phân hoạch là đại lượng tất định. Thời gian phụ thuộc vào phần cứng và chỉ có ba lượt đo cho mỗi chế độ.

Ở mức +5%, MILP theo cạnh tự tìm được nghiệm và chứng nhận tối ưu cho XSH-n20-k4-40 (540) và XSH-n20-k4-22 (592). Bảy ca còn lại hết thời gian với cận dưới, chưa thu được nghiệm khả thi độc lập. Khoảng cách giữa cận dưới và chi phí exact ở bảy ca này từ 1,58% đến 11,04%. Kết quả này phản ánh cấu hình MILP và ngân sách đã dùng.

## Kiểm tra ngoài họ XSH

Dùng mười instance đầu tiên theo số khách hàng của CVRPLIB bộ X (Uchoa và cộng sự). Với mỗi instance gốc, xáo trộn danh sách ID bằng Python 3.11 với seed 20261121, lấy hai nhóm rời nhau gồm 20 khách hàng đầu tiên và kế tiếp. Giữ depot, tọa độ, nhu cầu và khoảng cách EUC_2D. Mỗi bài dẫn xuất dùng bốn xe. Để bảo đảm có một phương án đóng tải, lần lượt xếp nhu cầu theo thứ tự giảm dần vào xe đang nhẹ nhất. Tải lớn nhất sau khi xếp là sức chứa cơ sở. Cách dựng này cho phép độ dư ban đầu dương. Các nghiệm của bài dẫn xuất chỉ áp dụng cho các khách hàng và sức chứa đã chọn. [CVRPLIB](https://galgos.inf.puc-rio.br/cvrplib/en/cvrp/instances)

Cộng thêm một đơn vị hoặc tăng 2%, 5% sức chứa cơ sở, làm tròn mức tăng lên số nguyên. Với sức chứa cơ sở nhỏ, nhiều nhãn kịch bản có thể cùng dẫn đến một sức chứa. Đo ba lượt mỗi chế độ, luân phiên thứ tự giữa các cặp. Dựng lại tour và đối chiếu chi phí cho cả hai chế độ. Các kịch bản có chung instance mẹ và cần được diễn giải như quan sát ghép cặp. Tệp kết quả lưu ID khách hàng, hash nguồn, độ dư, mục tiêu, số phân hoạch và thời gian từng lượt. [Dữ liệu thực nghiệm](results/external_ablation.csv)

Để tái lập, tải các tệp .vrp có tên trong PARENTS của external_ablation.py từ thư mục benchmarks/CVRP/X của [bản sao dữ liệu đã cố định commit](https://github.com/VROOM-Project/vroom-scripts/tree/0f5ee1eb625d287101686d11622d03e43ec0c969/benchmarks/CVRP/X), sau đó chạy:

```sh
"$PY" "$R/external_ablation.py" "$WORK/cvrplib-x" "$WORK/exact"
```

Áp dụng giới hạn 12 giây cho mỗi tiến trình gồm ba lượt đo sau khi phát hiện ca có nhu cầu lệch chạy lâu trong lượt thăm dò. Trên 60 cặp, 54 cặp hoàn thành và nhất quán về nghiệm cùng số phân hoạch. Sáu cặp thuộc X-n115-k10 chạm giới hạn ở ít nhất một chế độ. Trong 18 cặp hoàn thành mỗi kịch bản, trung vị tăng tốc toàn bộ lần lượt là 1,055× (+1), 1,031× (+2%) và 1,032× (+5%). Ở mức +1 chỉ 10/18 cặp nhanh hơn. Mức tăng tốc 4,45× quan sát trên XSH tại +1 không tái hiện ở trung vị của tập mẫu bên ngoài. Hai tập khác nhau cả về nhu cầu và tải dư ban đầu, nên phép thử này chưa tách riêng nguyên nhân của chênh lệch.

### Mở rộng phép thử sáu xe

Danh sách 20 instance mẹ giữ riêng nằm trong `holdout_parents.csv`. Xếp 97 tệp X trong bản sao VROOM cố định theo số nút, bỏ 10 tệp đầu đã dùng, chọn 20 vị trí cách đều gồm cả hai đầu của phần còn lại. Chọn trước khi giải. Mỗi instance mẹ cung cấp vị trí depot và 24 vị trí khách. Seed của nhóm mới tiếp nối 10 seed ban đầu; không thay đổi bộ sinh nhu cầu hoặc quy tắc 3+1. Có thể tải tệp gốc và chạy lại từ thư mục gốc repo như sau.

```sh
XDIR=/tmp/iccsa-holdout-vrp
mkdir -p "$XDIR"
cut -d, -f1 experiments/cita/holdout_parents.csv | tail -n +2 | while read -r parent; do
  curl -fsSL "https://raw.githubusercontent.com/VROOM-Project/vroom-scripts/0f5ee1eb625d287101686d11622d03e43ec0c969/benchmarks/CVRP/X/${parent}.vrp" -o "$XDIR/${parent}.vrp" || exit 1
done
python3.11 experiments/cita/six_vehicle_profiles.py "$XDIR" --holdout
python3.11 experiments/cita/holdout_summary.py --check-milp "$XDIR"
python3.11 experiments/cita/holdout_summary.py
```

Runner kiểm tra mã băm Git blob của cả 20 tệp trước khi tính. Bảng `six_vehicle_holdout.csv` ghi năm phương án cho mỗi ca hoàn tất và giữ dòng timeout cho ca quá hạn. Đơn vị mẫu là instance mẹ. Tỷ lệ giảm quãng đường tính trong từng ca rồi mới lấy trung vị. Bốn instance mẹ tại vị trí 1, 7, 14 và 20 của nhóm mới có thêm đối chiếu MILP. Các mốc thời gian chạy lại có thể thay đổi trạng thái chạm giới hạn của MILP.

### Phép ghép có khách mốc, chứng nhận và đợt chạy qua đêm

Đối chứng sáu tuyến dùng cùng đầu vào và cùng tập cột. Chế độ chuẩn giữ tất cả mặt nạ hai nửa. Hai chế độ còn lại giữ phía chứa tất cả 2 hoặc 3 khách mốc và phía chứa phần bù. Chúng xuất nghiệm, tổng số cách và chi phí tốt nhất cho từng lớp vượt tải. Phép thử chứng nhận LP riêng dùng nghiệm 3+1 đã lưu để đo độ chặt của cận. Chạy lại từ thư mục gốc:

```sh
python3.11 experiments/cita/anchor_ablation.py "$INITIAL_X_DIR" "$HOLDOUT_X_DIR"
python3.11 experiments/cita/regret_bound.py "$INITIAL_X_DIR" "$HOLDOUT_X_DIR"
python3.11 experiments/cita/summarize_anchors.py
```

Tác vụ `night-20261122` có bản nguồn, dữ liệu bố mẹ, mã băm, bản biên dịch và danh mục ca cố định trong `experiments/cita/runs/night-20261122/`. Đọc `REPORT.md` để xem đối chiếu theo nhánh; `status.json` ghi ca đang chạy và hạn dừng theo giờ Việt Nam; `jobs/` lưu từng checkpoint JSON bằng thay tệp nguyên tử. Dữ liệu của đợt này là bộ sinh tải chặt được ghi trong `src/overnight/cases.py`, khác bộ sinh của 30 ca sáu xe đầu tiên. Không gộp các ca vào số mẫu chính của paper trước khi phân tích.

Bộ DAG thử nghiệm xuất số đếm và mục tiêu theo lớp; thời gian của nó bao gồm công việc khác với bộ ghép có trả lại cả nghiệm. Đối chiếu tốc độ phải dùng cùng nhánh và đầu ra. Nhánh batch dùng cùng cấu trúc nhu cầu với ma trận khoảng cách khác nhau; nhánh policy giữ nguyên vị trí trong mỗi depot rồi thay nhu cầu. Nhánh certificate tính lại nghiệm khả thi từ cách đóng tải ban đầu bằng cải thiện hai tuyến, đưa cả thời gian tìm nghiệm và LP vào log. Trên macOS, launchd chạy một worker tại một thời điểm, có caffeinate giữ máy thức. Hạn 8 giờ tính từ lần khởi động đầu tiên và giữ nguyên khi tiếp tục. Mọi so sánh thời gian của chiến dịch dùng RSS được lấy mẫu và thời gian ở cấp tiến trình.

Lệnh kiểm tra của riêng đợt này:

```sh
launchctl print gui/501/local.iccsa.night-20261122
cat experiments/cita/runs/night-20261122/status.json
```

Nếu tiến trình bị ngắt trong khi phiên macOS vẫn còn đăng nhập và trước hạn dừng, dùng `launchctl kickstart gui/501/local.iccsa.night-20261122` để tiếp tục từ checkpoint. Giữ nắp laptop mở khi cắm điện. Có thể dừng có kiểm soát bằng cách tạo tệp `STOP` trong thư mục lần chạy. Job được nạp từ một plist trong workspace, không cài làm mục tự khởi động khi đăng nhập.
