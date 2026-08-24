# تصميم محرك الجدولة بـ OR-Tools CP-SAT (Phase B)

> تصميم طبقة جدولة مستقلة تعتمد CP-SAT، متوافقة مع النماذج الحالية في
> `school/models.py`، دون كسر الواجهات أو الحذف.

---

## 1. بنية الطبقة (Layered)

```
school/scheduling/
    __init__.py
    solver.py        # generate_schedule_cp(plan, ...) -> ScheduleResult
    constraints.py   # بناء القيود الصلبة + مصطلحات العقوبة التفضيلية
    objective.py      # تجميع دالة الهدف (Minimize penalty)
    validator.py     # ScheduleValidator: فحص جدول من DB
    diagnostics.py   # ScheduleDiagnostics: تفسير INFEASIBLE
    models.py         # (اختياري) أنواع مساعدة ScheduleResult
```

- **قاعدة الفصل:** `solver/constraints/objective/validator/diagnostics` لا تستورد Django views.
  تستورد فقط `school.models` و `ortools.sat.python`.
- **التوافق:** `school/scheduling_engine.py` يُبقي `generate_schedule()` و `evaluate_plan()`
  كدوال توافق تنادي الطبقة الجديدة (لكي لا تنكسر الاختبارات/الواجهات الحالية).

---

## 2. متغيرات القرار (Decision Variables)

لكل `TeachingLoad` (معرّف `tl_id`) ننشئ متغيرًا منطقيًا لكل خانة:

```
x[tl_id][day][period] ∈ {0,1}
```

المعنى: `x=1` ⇒ حصة من هذا النصاب موضوعة في (day, period).

ملاحظة: بما أن `tl` يمثّل ثلاثيًا فريدًا (معلم، مادة، صف)، فلا يمكن وضع أكثر من حصة واحدة
من نفس `tl` في نفس الخانة أصلًا (يمنعه قيد تداخل المعلم/الصف أدناه)، لذا المتغير المنطقي كافٍ
ولا حاجة لمتغيرات صحيحة.

نساعد أيضًا بمتغيرات مشتقّة:

```
y_teacher[t][day][period] = 1 إذا كان المعلم t يدرّس أي حصة في الخانة
y_class[c][day][period]   = 1 إذا كان الصف c لديه أي حصة في الخانة
```

يُعرّفان كـ `sum_{tl: teacher==t} x[tl] == 1 ⇒ y_teacher[t]=1` (باستخدام `AddBoolOr`/`OnlyEnforceIf`
أو `LinearConstraint` خطي: `y_teacher[t][d][p] <= sum x` و `sum x <= M*y`).

---

## 3. القيود الصلبة (Hard Constraints) — داخل Solver

1. **النصاب الأسبوعي (exact):**
   لكل `tl`: `sum_{day,period} x[tl][day][period] == tl.weekly_periods`.

2. **عدم تداخل المعلم:**
   لكل `(teacher t, day, period)`: `sum_{tl: teacher==t} x[tl][day][period] <= 1`.

3. **عدم تداخل الصف:**
   لكل `(class c, day, period)`: `sum_{tl: class==c} x[tl][day][period] <= 1`.

4. **التفريغ (Availability):**
   لكل `TeacherAvailability(teacher=t, day, period, available=False)`:
   `sum_{tl: teacher==t} x[tl][day][period] == 0` (أي يُمنع أي حصة للمعلم هناك).

5. **الحصص المثبتة (FixedLesson):**
   لكل `FixedLesson(teacher, subject, class, day, period)` نوجد `tl` المطابق
   `(teacher, subject, class)` ونفرض `x[tl][day][period] == 1`.

6. **الأيام/الحصص غير الفعّالة:**
   متغيرات `x` تُنشأ فقط لـ `active_days` و `active_periods`؛ لا توجد متغيرات لغير الفعّال،
   فلا يمكن وضع حصة هناك.

7. **قيود ScheduleConstraint بـ `type='hard'`:**
   تُطبَّق حسب `code` و `scope` (all / teachers / classes + M2M).
   - `max_periods_per_day` (hard): لكل (معلم/صف وفق النطاق) وكل يوم:
     `sum_{period} x[tl أو مجمل المعلم/الصف ذلك اليوم] <= weight`.
   - `max_consecutive` (hard): نافذة من `K+1` حصة متتالية للمعلم ⇒ `sum(y_teacher[t][d][p..p+K]) <= K`.
   - `spread_subject` (hard): لكل (معلم، مادة، صف) وكل يوم:
     `sum_{period} x[tl][day][period] <= max_per_day`.
   - `max_consecutive_gap` (hard): لكل يوم، أي نافذة طول `G+1` متتالية يجب أن تحتوي حصة واحدة
     على الأقل للمعلم (`sum(y) >= 1`) — تقترب من حد الفراغ (موثّقة).
   - `period_repeat` (hard): لكل (معلم، حصة محددة `period`) عدد الأيام ≤ `max_days`.

---

## 4. القيود التفضيلية (Soft Constraints) — penalties في Objective

لكل `ScheduleConstraint` بـ `type='soft'` (أو القيم الافتراضية عند غياب قيد) نضيف مصطلح عقوبة
يُقلَّل مجموعه:

- **فراغات المعلم داخل يومه:** عدد الفترات الحرة بين أول وآخر حصة للمعلم في اليوم.
- **الفراغات بين الحصص:** مجموع الفجوات في تسلسل حصص المعلم.
- **الحصص المتتالية فوق الحد:** تشغيل `max_consecutive` كعقوبة عند تجاوز الحد المفضّل.
- **تكرار المادة > مرة/يوم:** `spread_subject` كعقوبة.
- **عدم توزيع المادة على الأيام:** عقوبة إذا ركّزت المادة في أيام قليلة.
- **عدم توازن نصاب المعلم بين الأيام:** انحراف عدد حصص المعلم لكل يوم عن المتوسط.
- **الحصص الأولى/الأخيرة غير المرغوبة:** `avoid_first_last`.
- **أقصى فراغ متتالٍ:** `max_consecutive_gap` كعقوبة.

كل مصطلح = `bool_var * weight` أو تعبير خطي، يُجمع في `objective = Minimize(total_penalty)`.

**قاعدة صارمة:** أي Soft لا يخرق Hard. القيود الصلبة مفروضة دائمًا؛ الـ Soft يخفّض الجودة فقط.

---

## 5. دالة الهدف (Objective)

```
Minimize( total_penalty )
```

حيث `total_penalty = sum(soft_terms) + وزن رمزي لعدم وضع حصة` (لكل حصة غير موضوعة عقوبة كبيرة
تضمن وضع كل النصاب عند الإمكان؛ لكن النصاب مفروض كـ Hard صلب أصلًا، فلن تُترك حصة إن وُجد حل).

---

## 6. التنفيذ (Solver)

- `CpModel()` + `CP-SAT solver`.
- `max_time_in_seconds` قابل للضبط (افتراض 30 ثانية؛ قابل للرفع حسب حجم المدرسة).
- `solver.parameters.max_time_in_seconds = ...`
- `random_seed` يُمرَّر لإعادة الإنتاج (مع دعم اختبارات).
- الحالات:
  - `OPTIMAL` ⇒ حل مثالي.
  - `FEASIBLE` ⇒ حل يحقق كل Hard لكن غير مثالي ⇒ يُقبل مع إشارة.
  - `INFEASIBLE` ⇒ لا يوجد حل ⇒ `ScheduleDiagnostics` ي解释了 السبب.
  - `UNKNOWN` ⇒ تجاوز الوقت بلا ضمان ⇒ لا يُعتبر ناجحًا؛ تُعرض حالة واضحة.

---

## 7. التحقق المسبق (Pre-validation) — قبل تشغيل Solver

قبل بناء النموذج نفّذ فحصًا سريعًا ونعرض الخطأ مباشرةً إن وُجد تناقض واضح:
- لكل معلم: `required_total > available_periods_after_availability` ⇒ مستحيل.
- لكل صف: `required_total > active_days * active_periods` ⇒ مستحيل.
- `FixedLesson` يتعارض مع `TeacherAvailability` (غير متاح) ⇒ تعارض صريح.
- `FixedLesson` يتعارض مع `max_periods_per_day` (hard) ⇒ تعارض.

إن وُجد ⇒ لا نشغّل Solver؛ نعيد `INFEASIBLE` + أسباب.

---

## 8. التحقق اللاحق (ScheduleValidator)

يعمل على `ScheduleEntry` الموجودة فعلًا في DB (فيقدر يفحص برنامجًا قديمًا):
- `teacher conflicts`: معلم بحصتين في (day, period).
- `class conflicts`: صف بحصتين في (day, period).
- `availability violations`: حصة في خانة المعلم غير المتاح فيها.
- `required lesson count`: مجموع حصص كل (معلم، مادة، صف) == `weekly_periods`.
- `fixed lesson violations`: أي حصة مثبتة نُقلت.
- `hard constraints` من `ScheduleConstraint`.
- `invalid periods/days`: خانة خارج `active_days/periods`.

إن وُجد أي خرق Hard ⇒ الجدول غير صالح ⇒ لا يُحفظ.

---

## 9. التشخيص (ScheduleDiagnostics)

عند `INFEASIBLE` (أو فشل التحقق)، يُنتج قائمة أسباب بشرية:
- «المعلم X مطلوب منه N حصة، والفترات المتاحة له بعد التفريغ = M ⇒ مستحيل».
- «الصف Y لديه N حصة، وعدد الخانات الأسبوعية = active_days×active_periods = M ⇒ مستحيل».
- «حصة مثبتة للمعلم X يوم D حصة P، وهو غير متاح هناك ⇒ تعارض FixedLesson ↔ Availability».
- «القيد الصلب Z يتعارض مع الحصة المثبتة W».

---

## 10. الحفظ (Persistence)

- لا حفظ أثناء البحث.
- بعد الحل: نبني `entries` في الذاكرة، نمرّها على `ScheduleValidator`.
- إن صالحة ⇒ `transaction.atomic()`: `ScheduleEntry.objects.filter(plan=plan).delete()` ثم
  `bulk_create(entries)` (مع الحفاظ على البرنامج السابق آمنًا قبل التأكيد—يمكن عبر نسخة مسودّة).
- إن فشل التحقق ⇒ لا حفظ + رسالة فشل.
- `plan.hard_score=100`, `plan.soft_score` من النموذج، `plan.status='active'`.

---

## 11. التكامل (Integration)

- `schedule_generate` (view) يستدعي `generate_schedule(plan, ...)` (دالة التوافق) التي تندهي
  للطبقة الجديدة وتُرجع `ScheduleResult`.
- الرسالة للمستخدم تشمل: الحالة (نجاح/INFEASIBLE)، عدد المجدول/غير المجدول، Hard violations=0،
  Soft score، Solver status (OPTIMAL/FEASIBLE)، Solver time، والأسباب إن فشل.
- الزر الحالي «إنشاء البرنامج» يُعاد استخدامه (لا زر جديد).

---

## 12. الخرج المتوقع (ScheduleResult)

```
{
  'status': 'SUCCESS' | 'INFEASIBLE' | 'UNKNOWN',
  'solver_status': 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN',
  'entries': [ {day, period, teacher, subject, class, fixed}, ... ],
  'unscheduled': [...],          # فارغ عند النجاح
  'hard_violations': 0,
  'soft_score': float,
  'solver_time': float,
  'diagnostics': [ 'سبب1', ... ],
  'stats': { required, scheduled, days, periods },
}
```

---

## 13. ملاحظات نشر OR-Tools

- `ortools` يُضاف إلى `requirements.txt`.
- على Vercel: حزمة أصلية كبيرة؛ يُنصح بالتحقق من حدود حجم دالة Vercel. إن تعذّر، يُمكن تعطيل
  CP-SAT واستخدام بديل (لكن المواصفات تمنع الرجوع إلى Greedy).
- محليًا/على خادم عادي: يعمل بلا مشكلة (مثبّت بنجاح على Python 3.12).
