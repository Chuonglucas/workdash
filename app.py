from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Cấu hình database — lưu vào file workdash.db
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///workdash.db"
db = SQLAlchemy(app)

# Định nghĩa bảng CongViec trong database
class CongViec(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    ten      = db.Column(db.String(200), nullable=False)
    nguoi    = db.Column(db.String(100), nullable=False)
    trang_thai = db.Column(db.String(50), default="Chưa bắt đầu")

# Tạo database và nhập dữ liệu mẫu
def tao_du_lieu_mau():
    mau = [
        CongViec(ten="Thiết kế UI dashboard", nguoi="An", trang_thai="Xong"),
        CongViec(ten="Kết nối database",       nguoi="Bình", trang_thai="Đang làm"),
        CongViec(ten="Viết API báo cáo",       nguoi="An", trang_thai="Chưa bắt đầu"),
        CongViec(ten="Kiểm thử tính năng lọc", nguoi="Châu", trang_thai="Đang làm"),
    ]
    db.session.add_all(mau)
    db.session.commit()

@app.route("/")
def trang_chu():
    # Đọc toàn bộ công việc từ database
    ds_cong_viec = CongViec.query.all()

    # Tính toán số liệu
    tong          = len(ds_cong_viec)
    hoan_thanh    = len([cv for cv in ds_cong_viec if cv.trang_thai == "Xong"])
    dang_lam      = len([cv for cv in ds_cong_viec if cv.trang_thai == "Đang làm"])
    ton_dong      = len([cv for cv in ds_cong_viec if cv.trang_thai == "Chưa bắt đầu"])

    return render_template("index.html",
        cong_viec  = ds_cong_viec,
        tong       = tong,
        hoan_thanh = hoan_thanh,
        dang_lam   = dang_lam,
        ton_dong   = ton_dong
    )
# Route mới — nhận dữ liệu từ form
@app.route("/them", methods=["POST"])
def them_cong_viec():
    ten        = request.form.get("ten")
    nguoi      = request.form.get("nguoi")
    trang_thai = request.form.get("trang_thai")
    cong_viec_moi = CongViec(ten=ten, nguoi=nguoi, trang_thai=trang_thai)
    db.session.add(cong_viec_moi)
    db.session.commit()
    return redirect(url_for("trang_chu"))
# Route xóa công việc
@app.route("/xoa/<int:id>", methods=["POST"])
def xoa_cong_viec(id):
    cv = CongViec.query.get_or_404(id)
    db.session.delete(cv)
    db.session.commit()
    return jsonify({"ok": True})

# Route đổi trạng thái
@app.route("/doi-trang-thai/<int:id>", methods=["POST"])
def doi_trang_thai(id):
    cv    = CongViec.query.get_or_404(id)
    vong  = ["Chưa bắt đầu", "Đang làm", "Xong"]
    vi_tri_hien_tai = vong.index(cv.trang_thai)
    cv.trang_thai   = vong[(vi_tri_hien_tai + 1) % len(vong)]
    db.session.commit()
    return jsonify({"ok": True, "trang_thai_moi": cv.trang_thai})
# Route tìm kiếm — trả về JSON cho JavaScript
@app.route("/tim-kiem")
def tim_kiem():
    tu_khoa    = request.args.get("q", "").strip()
    trang_thai = request.args.get("trang_thai", "").strip()

    # Bắt đầu query
    query = CongViec.query

    # Lọc theo từ khóa nếu có
    if tu_khoa:
        query = query.filter(
            CongViec.ten.ilike(f"%{tu_khoa}%") |
            CongViec.nguoi.ilike(f"%{tu_khoa}%")
        )

    # Lọc theo trạng thái nếu có
    if trang_thai:
        query = query.filter(CongViec.trang_thai == trang_thai)

    ket_qua = query.all()

    # Trả về JSON cho JavaScript
    return jsonify([{
        "id":         cv.id,
        "ten":        cv.ten,
        "nguoi":      cv.nguoi,
        "trang_thai": cv.trang_thai
    } for cv in ket_qua])
# ---- ROUTE MỚI: Stream dữ liệu real-time ----
def tao_du_lieu_realtime():
    """Hàm generator — chạy mãi, cứ 5 giây đẩy dữ liệu mới xuống"""
    while True:
        with app.app_context():
            ds = CongViec.query.all()
            # Đếm theo từng người phụ trách
            nguoi_dict = {}
            for cv in ds:
                if cv.nguoi not in  nguoi_dict:
                    nguoi_dict[cv.nguoi] = {"hoan_thanh": 0, "dang_lam": 0,"ton_dong": 0}
                if cv.trang_thai == "Xong":
                    nguoi_dict[cv.nguoi]["hoan_thanh"] += 1
                elif cv.trang_thai == "Đang làm":
                    nguoi_dict[cv.nguoi]["dang_lam"] += 1
                else:
                    nguoi_dict[cv.nguoi]["ton_dong"] += 1
            du_lieu = {
                # Metric cards
                "tong":       len(ds),
                "hoan_thanh": len([cv for cv in ds if cv.trang_thai == "Xong"]),
                "dang_lam":   len([cv for cv in ds if cv.trang_thai == "Đang làm"]),
                "ton_dong":   len([cv for cv in ds if cv.trang_thai == "Chưa bắt đầu"]),
                "thoi_gian":  time.strftime("%H:%M:%S"),

                # Dữ liệu biểu đồ theo người phụ trách
                "bieu_do": {
                    "nhan": list(nguoi_dict.keys()),
                    "hoan_thanh": [v["hoan_thanh"] for v in nguoi_dict.values()],
                    "dang_lam":   [v["dang_lam"]   for v in nguoi_dict.values()],
                    "ton_dong":   [v["ton_dong"]    for v in nguoi_dict.values()], 
               }
            }
        yield f"data: {json.dumps(du_lieu, ensure_ascii=False)}\n\n"
        time.sleep(5)
        
@app.route("/stream")
def stream():
    return Response(
        tao_du_lieu_realtime(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
if __name__ == "__main__":
    with app.app_context():
        db.create_all()           # Tạo bảng nếu chưa có
        if CongViec.query.count() == 0:
            tao_du_lieu_mau()     # Nhập dữ liệu mẫu lần đầu
    app.run(debug=True)