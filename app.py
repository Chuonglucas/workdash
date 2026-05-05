from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
import json
import time
import os
import pandas as pd

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///workdash.db"
app.config["UPLOAD_FOLDER"] = "uploads"
db = SQLAlchemy(app)

class CongViec(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    ten        = db.Column(db.String(200), nullable=False)
    nguoi      = db.Column(db.String(100), nullable=False)
    trang_thai = db.Column(db.String(50), default="Chưa bắt đầu")

@app.route("/")
def trang_chu():
    ds_cong_viec = CongViec.query.all()
    tong         = len(ds_cong_viec)
    hoan_thanh   = len([cv for cv in ds_cong_viec if cv.trang_thai == "Xong"])
    dang_lam     = len([cv for cv in ds_cong_viec if cv.trang_thai == "Đang làm"])
    ton_dong     = len([cv for cv in ds_cong_viec if cv.trang_thai == "Chưa bắt đầu"])
    return render_template("index.html",
        cong_viec  = ds_cong_viec,
        tong       = tong,
        hoan_thanh = hoan_thanh,
        dang_lam   = dang_lam,
        ton_dong   = ton_dong
    )

@app.route("/them", methods=["POST"])
def them_cong_viec():
    ten        = request.form.get("ten")
    nguoi      = request.form.get("nguoi")
    trang_thai = request.form.get("trang_thai")
    db.session.add(CongViec(ten=ten, nguoi=nguoi, trang_thai=trang_thai))
    db.session.commit()
    return redirect(url_for("trang_chu"))

@app.route("/xoa/<int:id>", methods=["POST"])
def xoa_cong_viec(id):
    cv = CongViec.query.get_or_404(id)
    db.session.delete(cv)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/doi-trang-thai/<int:id>", methods=["POST"])
def doi_trang_thai(id):
    cv   = CongViec.query.get_or_404(id)
    vong = ["Chưa bắt đầu", "Đang làm", "Xong"]
    cv.trang_thai = vong[(vong.index(cv.trang_thai) + 1) % len(vong)]
    db.session.commit()
    return jsonify({"ok": True, "trang_thai_moi": cv.trang_thai})

@app.route("/tim-kiem")
def tim_kiem():
    tu_khoa    = request.args.get("q", "").strip()
    trang_thai = request.args.get("trang_thai", "").strip()
    query      = CongViec.query
    if tu_khoa:
        query = query.filter(
            CongViec.ten.ilike(f"%{tu_khoa}%") |
            CongViec.nguoi.ilike(f"%{tu_khoa}%")
        )
    if trang_thai:
        query = query.filter(CongViec.trang_thai == trang_thai)
    ket_qua = query.all()
    return jsonify([{
        "id": cv.id, "ten": cv.ten,
        "nguoi": cv.nguoi, "trang_thai": cv.trang_thai
    } for cv in ket_qua])

def tao_du_lieu_realtime():
    while True:
        with app.app_context():
            ds = CongViec.query.all()
            nguoi_dict = {}
            for cv in ds:
                if cv.nguoi not in nguoi_dict:
                    nguoi_dict[cv.nguoi] = {"hoan_thanh": 0, "dang_lam": 0, "ton_dong": 0}
                if cv.trang_thai == "Xong":
                    nguoi_dict[cv.nguoi]["hoan_thanh"] += 1
                elif cv.trang_thai == "Đang làm":
                    nguoi_dict[cv.nguoi]["dang_lam"] += 1
                else:
                    nguoi_dict[cv.nguoi]["ton_dong"] += 1

            du_lieu = {
                "tong":       len(ds),
                "hoan_thanh": len([cv for cv in ds if cv.trang_thai == "Xong"]),
                "dang_lam":   len([cv for cv in ds if cv.trang_thai == "Đang làm"]),
                "ton_dong":   len([cv for cv in ds if cv.trang_thai == "Chưa bắt đầu"]),
                "thoi_gian":  time.strftime("%H:%M:%S"),
                "bieu_do": {
                    "nhan":       list(nguoi_dict.keys()),
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# ---- ROUTE MỚI: Upload file Excel/CSV ----
@app.route("/upload", methods=["POST"])
def upload_file():
    # Kiểm tra có file không
    if "file" not in request.files:
        return jsonify({"ok": False, "loi": "Không tìm thấy file"})

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"ok": False, "loi": "Chưa chọn file"})

    # Kiểm tra định dạng file
    ten_file = file.filename.lower()
    if not (ten_file.endswith(".xlsx") or ten_file.endswith(".csv")):
        return jsonify({"ok": False, "loi": "Chỉ chấp nhận file .xlsx hoặc .csv"})

    try:
        # Đọc file bằng Pandas
        if ten_file.endswith(".xlsx"):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file, encoding="utf-8")

        # Kiểm tra đủ cột chưa
        cot_can = ["ten", "nguoi", "trang_thai"]
        for cot in cot_can:
            if cot not in df.columns:
                return jsonify({
                    "ok": False,
                    "loi": f"File thiếu cột '{cot}'. Cần có: ten, nguoi, trang_thai"
                })

        # Xóa dữ liệu cũ nếu người dùng muốn
        xoa_cu = request.form.get("xoa_cu") == "true"
        if xoa_cu:
            CongViec.query.delete()

        # Đọc từng hàng và thêm vào database
        dem = 0
        for _, hang in df.iterrows():
            ten        = str(hang["ten"]).strip()
            nguoi      = str(hang["nguoi"]).strip()
            trang_thai = str(hang["trang_thai"]).strip()

            # Bỏ qua hàng rỗng
            if not ten or ten == "nan":
                continue

            # Chuẩn hóa trạng thái
            if trang_thai not in ["Xong", "Đang làm", "Chưa bắt đầu"]:
                trang_thai = "Chưa bắt đầu"

            db.session.add(CongViec(
                ten=ten, nguoi=nguoi, trang_thai=trang_thai
            ))
            dem += 1

        db.session.commit()
        return jsonify({"ok": True, "dem": dem})

    except Exception as e:
        return jsonify({"ok": False, "loi": str(e)})

# ---- ROUTE MỚI: Phân tích dữ liệu ----
@app.route("/phan-tich")
def phan_tich():
    ds = CongViec.query.all()

    if not ds:
        return jsonify({"ok": False, "loi": "Chưa có dữ liệu"})

    # Chuyển sang DataFrame để phân tích
    df = pd.DataFrame([{
        "id":         cv.id,
        "ten":        cv.ten,
        "nguoi":      cv.nguoi,
        "trang_thai": cv.trang_thai
    } for cv in ds])

    # 1. Hiệu suất theo người
    hieu_suat = []
    for nguoi, nhom in df.groupby("nguoi"):
        tong_nguoi     = len(nhom)
        xong_nguoi     = len(nhom[nhom["trang_thai"] == "Xong"])
        ty_le          = round((xong_nguoi / tong_nguoi) * 100) if tong_nguoi > 0 else 0
        hieu_suat.append({
            "nguoi":      nguoi,
            "tong":       tong_nguoi,
            "hoan_thanh": xong_nguoi,
            "ty_le":      ty_le
        })

    # Sắp xếp theo tỉ lệ hoàn thành giảm dần
    hieu_suat.sort(key=lambda x: x["ty_le"], reverse=True)

    # 2. Thống kê tổng
    tong          = len(df)
    hoan_thanh    = len(df[df["trang_thai"] == "Xong"])
    dang_lam      = len(df[df["trang_thai"] == "Đang làm"])
    ton_dong      = len(df[df["trang_thai"] == "Chưa bắt đầu"])
    ty_le_chung   = round((hoan_thanh / tong) * 100) if tong > 0 else 0

    # 3. Người làm nhiều nhất
    nguoi_nhieu   = df.groupby("nguoi").size().idxmax()
    so_nhieu      = df.groupby("nguoi").size().max()

    # 4. Người hiệu quả nhất (tỉ lệ hoàn thành cao nhất, có ít nhất 1 công việc)
    hieu_qua_nhat = hieu_suat[0] if hieu_suat else None

    # 5. Cảnh báo tồn đọng nhiều
    canh_bao = []
    for nguoi, nhom in df.groupby("nguoi"):
        ton = len(nhom[nhom["trang_thai"] == "Chưa bắt đầu"])
        if ton >= 2:
            canh_bao.append({"nguoi": nguoi, "so_ton_dong": ton})
    canh_bao.sort(key=lambda x: x["so_ton_dong"], reverse=True)

    return jsonify({
        "ok": True,
        "tong_quan": {
            "tong":        tong,
            "hoan_thanh":  hoan_thanh,
            "dang_lam":    dang_lam,
            "ton_dong":    ton_dong,
            "ty_le_chung": ty_le_chung
        },
        "hieu_suat":      hieu_suat,
        "nguoi_nhieu":    {"ten": nguoi_nhieu, "so": int(so_nhieu)},
        "hieu_qua_nhat":  hieu_qua_nhat,
        "canh_bao":       canh_bao
    })
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, threaded=True)