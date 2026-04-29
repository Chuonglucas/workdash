from flask import Flask, render_template
import json
app = Flask (__name__)
# Dữ liệu giả - sau này sẽ lấy từ database thật
du_lieu = {
    "tong_cong_viec": 24,
    "hoan_thanh": 18,
    "dang_lam": 4,
    "ton_dong": 2,
    "cong_viec": [
        {"ten": "Thiết kế UI dashboard", "nguoi": "An", "trang_thai": "xong"},
        {"ten": "kết nối database", "nguoi": "Binh", "trang_thai": "Đang làm"},
        {"ten": "Viết API báo cáo", "nguoi": "An", "trang_thai": "Chưa bắt đầu"},
        {"ten": "Kiểm thử tính năng lọc", "nguoi": "Châu", "trang_thai": "Đang làm"},
    ],
    # Dữ liệu cho biểu đồ
    "bieu_do": {
        "nhan": ["Tuần 1", "Tuần 2", "Tuần 3", "Tuần 4"],
        "hoan_thanh": [3, 7, 20, 25],
        "dang_lam": [5, 4, 3, 4]
    }
}
@app.route("/")
def trang_chu ():
    # Chuyển dữ liệu Python -> JSON để JavaScript đọc được
    bieu_do_json = json.dumps (du_lieu["bieu_do"])
    return render_template ("index.html", data=du_lieu, bieu_do=bieu_do_json)
if __name__ == "__main__":
    app.run (debug=True)