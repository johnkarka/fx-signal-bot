from flask import Blueprint, render_template, request, jsonify

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('form.html')

@bp.route('/form-test')
def form_test():
    return render_template('form.html')

@bp.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()
    print("✅ Received data:", data)
    return jsonify({"status": "success", "data": data}), 200