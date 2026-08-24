from ortools.sat.python import cp_model as cp


def assemble(model, penalties):
    """يضيف دالة الهدف: تصغير مجموع العقوبات (القيود التفضيلية)."""
    if penalties:
        model.Minimize(sum(expr * w for expr, w in penalties))
    else:
        model.Minimize(0)
