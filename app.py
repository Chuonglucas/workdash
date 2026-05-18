from flask import (Flask, render_template, request,
                   redirect, url_for, jsonify, Response, send_file)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin,
                         login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
import json, time, io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                 Spacer, Table, TableStyle, Image)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///workdash.db"
app.config["SECRET_KEY"] = "workdash-secret-2024"   # Dùng để mã hóa session
db = SQLAlchemy(app)

# Khởi tạo Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "trang_login"   # Chuyển về đây nếu chưa đăng nhập

# =============================================
# MODELS — Bảng database
# =============================================
class NguoiDung(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    ten_dang_nhap = db.Column(db.String(80), unique=True, nullable=False)
    mat_khau      = db.Column(db.String(200), nullable=False)
    ho_ten        = db.Column(db.String(100), nullable=False)
    vai_tro       = db.Column(db.String(20), default="user")  # "admin" hoặc "user"

    def dat_mat_khau(self, mk):
        self.mat_khau = generate_password_hash(mk)

    def kiem_tra_mat_khau(self, mk):
        return check_password_hash(self.mat_khau, mk)

class CongViec(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    ten           = db.Column(db.String(200), nullable=False)
    nguoi         = db.Column(db.String(100), nullable=False)
    trang_thai    = db.Column(db.String(50), default="Chưa bắt đầu")
    nguoi_dung_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id"))

@login_manager.user_loader
def load_user(user_id):
    return NguoiDung.query.get(int(user_id))

# =============================================
# ROUTES — Đăng nhập / Đăng xuất
# =============================================
@app.route("/login", methods=["GET", "POST"])
def trang_login():
    # Nếu đã đăng nhập rồi thì về trang chủ
    if current_user.is_authenticated:
        return redirect(url_for("trang_chu"))

    loi = None
    if request.method == "POST":
        ten_dn = request.form.get("ten_dang_nhap")
        mk     = request.form.get("mat_khau")
        nguoi  = NguoiDung.query.filter_by(ten_dang_nhap=ten_dn).first()

        if nguoi and nguoi.kiem_tra_mat_khau(mk):
            login_user(nguoi)
            return redirect(url_for("trang_chu"))
        else:
            loi = "Tên đăng nhập hoặc mật khẩu không đúng"

    return render_template("login.html", loi=loi)

@app.route("/logout")
@login_required
def dang_xuat():
    logout_user()
    return redirect(url_for("trang_login"))

# =============================================
# ROUTES — Dashboard chính
# =============================================
@app.route("/")
@login_required      # Phải đăng nhập mới vào được
def trang_chu():
    # Admin thấy tất cả, user thường chỉ thấy của mình
    if current_user.vai_tro == "admin":
        ds_cong_viec = CongViec.query.all()
    else:
        ds_cong_viec = CongViec.query.filter_by(
            nguoi=current_user.ho_ten
        ).all()

    tong       = len(ds_cong_viec)
    hoan_thanh = len([cv for cv in ds_cong_viec if cv.trang_thai == "Xong"])
    dang_lam   = len([cv for cv in ds_cong_viec if cv.trang_thai == "Đang làm"])
    ton_dong   = len([cv for cv in ds_cong_viec if cv.trang_thai == "Chưa bắt đầu"])

    return render_template("index.html",
        cong_viec  = ds_cong_viec,
        tong       = tong,
        hoan_thanh = hoan_thanh,
        dang_lam   = dang_lam,
        ton_dong   = ton_dong
    )

@app.route("/them", methods=["POST"])
@login_required
def them_cong_viec():
    ten        = request.form.get("ten")
    nguoi      = request.form.get("nguoi")
    trang_thai = request.form.get("trang_thai")
    db.session.add(CongViec(
        ten=ten, nguoi=nguoi,
        trang_thai=trang_thai,
        nguoi_dung_id=current_user.id
    ))
    db.session.commit()
    return redirect(url_for("trang_chu"))

@app.route("/xoa/<int:id>", methods=["POST"])
@login_required
def xoa_cong_viec(id):
    cv = CongViec.query.get_or_404(id)
    # User thường chỉ xóa được công việc của mình
    if current_user.vai_tro != "admin" and cv.nguoi != current_user.ho_ten:
        return jsonify({"ok": False, "loi": "Không có quyền xóa"})
    db.session.delete(cv)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/doi-trang-thai/<int:id>", methods=["POST"])
@login_required
def doi_trang_thai(id):
    cv   = CongViec.query.get_or_404(id)
    vong = ["Chưa bắt đầu", "Đang làm", "Xong"]
    cv.trang_thai = vong[(vong.index(cv.trang_thai) + 1) % len(vong)]
    db.session.commit()
    return jsonify({"ok": True, "trang_thai_moi": cv.trang_thai})

@app.route("/tim-kiem")
@login_required
def tim_kiem():
    tu_khoa    = request.args.get("q", "").strip()
    trang_thai = request.args.get("trang_thai", "").strip()

    if current_user.vai_tro == "admin":
        query = CongViec.query
    else:
        query = CongViec.query.filter_by(nguoi=current_user.ho_ten)

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

@app.route("/phan-tich")
@login_required
def phan_tich():
    if current_user.vai_tro == "admin":
        ds = CongViec.query.all()
    else:
        ds = CongViec.query.filter_by(nguoi=current_user.ho_ten).all()

    if not ds:
        return jsonify({"ok": False, "loi": "Chưa có dữ liệu"})

    df = pd.DataFrame([{
        "ten": cv.ten, "nguoi": cv.nguoi, "trang_thai": cv.trang_thai
    } for cv in ds])

    tong       = len(df)
    hoan_thanh = len(df[df["trang_thai"] == "Xong"])
    dang_lam   = len(df[df["trang_thai"] == "Đang làm"])
    ton_dong   = len(df[df["trang_thai"] == "Chưa bắt đầu"])
    ty_le      = round((hoan_thanh / tong) * 100) if tong > 0 else 0

    hieu_suat = []
    for nguoi, nhom in df.groupby("nguoi"):
        t  = len(nhom)
        ht = len(nhom[nhom["trang_thai"] == "Xong"])
        hieu_suat.append({
            "nguoi": nguoi, "tong": t, "hoan_thanh": ht,
            "ty_le": round((ht / t) * 100) if t > 0 else 0
        })
    hieu_suat.sort(key=lambda x: x["ty_le"], reverse=True)

    canh_bao = []
    for nguoi, nhom in df.groupby("nguoi"):
        ton = len(nhom[nhom["trang_thai"] == "Chưa bắt đầu"])
        if ton >= 2:
            canh_bao.append({"nguoi": nguoi, "so_ton_dong": ton})

    return jsonify({
        "ok": True,
        "tong_quan": {
            "tong": tong, "hoan_thanh": hoan_thanh,
            "dang_lam": dang_lam, "ton_dong": ton_dong,
            "ty_le_chung": ty_le
        },
        "hieu_suat":     hieu_suat,
        "nguoi_nhieu":   hieu_suat[0] if hieu_suat else {},
        "hieu_qua_nhat": hieu_suat[0] if hieu_suat else {},
        "canh_bao":      canh_bao
    })

def tao_du_lieu_realtime():
    while True:
        with app.app_context():
            ds = CongViec.query.all()
            nguoi_dict = {}
            for cv in ds:
                if cv.nguoi not in nguoi_dict:
                    nguoi_dict[cv.nguoi] = {
                        "hoan_thanh": 0, "dang_lam": 0, "ton_dong": 0
                    }
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
@login_required
def stream():
    return Response(
        tao_du_lieu_realtime(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "loi": "Không tìm thấy file"})
    file = request.files["file"]
    ten_file = file.filename.lower()
    if not (ten_file.endswith(".xlsx") or ten_file.endswith(".csv")):
        return jsonify({"ok": False, "loi": "Chỉ chấp nhận .xlsx hoặc .csv"})
    try:
        df = pd.read_excel(file) if ten_file.endswith(".xlsx") \
             else pd.read_csv(file, encoding="utf-8")
        for cot in ["ten", "nguoi", "trang_thai"]:
            if cot not in df.columns:
                return jsonify({"ok": False, "loi": f"Thiếu cột '{cot}'"})
        if request.form.get("xoa_cu") == "true":
            CongViec.query.delete()
        dem = 0
        for _, hang in df.iterrows():
            ten = str(hang["ten"]).strip()
            if not ten or ten == "nan":
                continue
            ts = str(hang["trang_thai"]).strip()
            if ts not in ["Xong", "Đang làm", "Chưa bắt đầu"]:
                ts = "Chưa bắt đầu"
            db.session.add(CongViec(
                ten=ten, nguoi=str(hang["nguoi"]).strip(),
                trang_thai=ts, nguoi_dung_id=current_user.id
            ))
            dem += 1
        db.session.commit()
        return jsonify({"ok": True, "dem": dem})
    except Exception as e:
        return jsonify({"ok": False, "loi": str(e)})

@app.route("/xuat-pdf")
@login_required
def xuat_pdf():
    if current_user.vai_tro == "admin":
        ds = CongViec.query.all()
    else:
        ds = CongViec.query.filter_by(nguoi=current_user.ho_ten).all()

    if not ds:
        return "Chưa có dữ liệu", 400

    df = pd.DataFrame([{
        "ten": cv.ten, "nguoi": cv.nguoi, "trang_thai": cv.trang_thai
    } for cv in ds])

    tong       = len(df)
    hoan_thanh = len(df[df["trang_thai"] == "Xong"])
    dang_lam   = len(df[df["trang_thai"] == "Đang làm"])
    ton_dong   = len(df[df["trang_thai"] == "Chưa bắt đầu"])
    ty_le      = round((hoan_thanh / tong) * 100) if tong > 0 else 0

    hieu_suat = []
    for nguoi, nhom in df.groupby("nguoi"):
        t  = len(nhom)
        ht = len(nhom[nhom["trang_thai"] == "Xong"])
        hieu_suat.append({
            "nguoi": nguoi, "tong": t, "xong": ht,
            "ty_le": round((ht / t) * 100) if t > 0 else 0
        })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    nhan = ["Hoàn thành", "Đang làm", "Tồn đọng"]
    so   = [hoan_thanh, dang_lam, ton_dong]
    mau  = ["#22c55e", "#3b82f6", "#f87171"]
    ax1.pie(so, labels=nhan, colors=mau, autopct="%1.0f%%", startangle=90)
    ax1.set_title("Tỉ lệ trạng thái", fontsize=13)

    ten_nguoi   = [h["nguoi"] for h in hieu_suat]
    ty_le_nguoi = [h["ty_le"] for h in hieu_suat]
    mau_cot = ["#22c55e" if t >= 70 else "#f59e0b" if t >= 40
               else "#f87171" for t in ty_le_nguoi]
    bars = ax2.bar(ten_nguoi, ty_le_nguoi, color=mau_cot, width=0.5)
    ax2.set_ylim(0, 110)
    ax2.set_title("Hiệu suất theo người", fontsize=13)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for bar, val in zip(bars, ty_le_nguoi):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 2, f"{val}%", ha="center", fontsize=10)
    plt.tight_layout()

    buf_bieu_do = io.BytesIO()
    plt.savefig(buf_bieu_do, format="png", dpi=150, bbox_inches="tight")
    buf_bieu_do.seek(0)
    plt.close()

    buf_pdf = io.BytesIO()
    doc     = SimpleDocTemplate(buf_pdf, pagesize=A4,
                                 leftMargin=2*cm, rightMargin=2*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
    styles  = getSampleStyleSheet()
    el      = []

    el.append(Paragraph("WorkDash — Báo cáo tổng hợp",
        ParagraphStyle("h1", parent=styles["Title"],
                       fontSize=22, textColor=colors.HexColor("#1d4ed8"),
                       spaceAfter=6)))
    el.append(Paragraph(
        f"Xuất ngày {time.strftime('%d/%m/%Y %H:%M')} · "
        f"Người dùng: {current_user.ho_ten} · "
        f"Tổng {tong} công việc · Hoàn thành {ty_le}%",
        ParagraphStyle("sub", parent=styles["Normal"],
                       fontSize=10, textColor=colors.HexColor("#6b7280"),
                       spaceAfter=20)))

    el.append(Paragraph("Biểu đồ phân tích",
        ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13,
                       spaceBefore=16, spaceAfter=8)))
    el.append(Image(buf_bieu_do, width=16*cm, height=6.4*cm))

    el.append(Paragraph("Danh sách công việc",
        ParagraphStyle("h2b", parent=styles["Heading2"], fontSize=13,
                       spaceBefore=16, spaceAfter=8)))
    data_cv = [["STT", "Tên công việc", "Người phụ trách", "Trạng thái"]]
    for i, cv in enumerate(ds, 1):
        data_cv.append([str(i), cv.ten, cv.nguoi, cv.trang_thai])
    bang = Table(data_cv, colWidths=[1.5*cm, 8*cm, 4*cm, 3.5*cm])
    bang.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#374151")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ALIGN",         (0, 0), (0, -1),  "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    el.append(bang)
    el.append(Spacer(1, 20))
    el.append(Paragraph(
        f"Tạo tự động bởi WorkDash · {time.strftime('%d/%m/%Y %H:%M:%S')}",
        ParagraphStyle("footer", parent=styles["Normal"],
                       fontSize=8, textColor=colors.HexColor("#9ca3af"),
                       alignment=1)))
    doc.build(el)
    buf_pdf.seek(0)

    return send_file(buf_pdf, mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"WorkDash_{time.strftime('%d%m%Y_%H%M')}.pdf")

# =============================================
# KHỞI TẠO DATABASE + TÀI KHOẢN MẶC ĐỊNH
# =============================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Tạo tài khoản admin mặc định nếu chưa có
        if not NguoiDung.query.filter_by(ten_dang_nhap="admin").first():
            admin = NguoiDung(
                ten_dang_nhap = "admin",
                ho_ten        = "Admin",
                vai_tro       = "admin"
            )
            admin.dat_mat_khau("admin123")
            db.session.add(admin)

            # Tạo thêm 2 user mẫu
            for ten, hoten in [("an", "An"), ("binh", "Bình")]:
                u = NguoiDung(ten_dang_nhap=ten, ho_ten=hoten, vai_tro="user")
                u.dat_mat_khau("123456")
                db.session.add(u)

            db.session.commit()
            print("Đã tạo tài khoản mặc định!")

    app.run(debug=True, threaded=True)