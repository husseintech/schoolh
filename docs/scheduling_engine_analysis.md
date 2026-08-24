# تحليل محرك إنشاء الجدول الأسبوعي (Phase A)

> تحليل المشروع الحالي قبل أي تعديل كود. الغرض: فهم النماذج والقيود ومسار التوليد،
> وتحديد سبب عجز المحرك الحالي عن إعطاء جدول صالح، ثم التوصية بالحل (OR-Tools CP-SAT).

---

## 1. البيئة والاعتماديات

- Python: **3.12.10**
- Django: **6.0.7**
- مدير الحزم: `requirements.txt` (لا يحتوي `ortools` حاليًا).
- OR-Tools: **تم التحقق من إمكانية التثبيت** → `ortools==9.15.6755` يُثبَّت بنجاح على Python 3.12 (Windows).
  إذًا استخدام CP-SAT ممكن تقنيًا في بيئة التطوير.
- ملاحظة نشر: الخادم المنشور على Vercel (Python runtime + Postgres). `ortools` حزمة أصلية كبيرة؛
  يُنصح بالتحقق من حدود حجم دالة Vercel عند النشر، لكنها تعمل عادةً. (تفصيل النشر ضمن Phase C/G.)
- لا يوجد DRF/serializers في المشروع؛ كل التعامل عبر Django views + قوالب.
- لا يوجد ملف JS خارجي مخصص للجدول؛ كل المنطق التفاعلي داخل القوالب (إن وجد).

---

## 2. النماذج المعنية (school/models.py)

### 2.1 SchedulePlan
- الحقول: `name, version_label, academic_year, semester, days(JSONField), periods(JSONField),
  breaks(JSONField), status, hard_score, soft_score, generated_at, created_by`.
- `days` / `periods` مصفوفات من قواميس، كل عنصر فيه `{'idx' أو 'name', 'active': True}`.
- الخصائص: `active_days` (الأيام الفعّالة فقط)، `active_periods`، `total_required_periods`.
- **مهم:** عدد الخانات المتاحة لكل صف = `len(active_days) * len(active_periods)`.

### 2.2 TeachingLoad (النصاب)
- `plan, teacher, subject, student_class, weekly_periods, semester`.
- قيد فريد: `(plan, teacher, subject, student_class)`.
- هذا هو المصدر الأساسي لعدد الحصص المطلوبة لكل (معلم، مادة، صف).

### 2.3 TeacherAvailability (التفريغ)
- `plan, teacher, day, period, available (BooleanField, افتراضي True)`.
- `available=False` يعني المعلم غير متاح في هذه الخانة.
- المفتاح الطبيعي: `(plan, teacher, day, period)`.

### 2.4 ScheduleConstraint (القيود)
- الحقول: `plan, code, type('hard'/'soft'), name, description, scope('all'/'teachers'/'classes'),
  weight(Integer), params(JSONField), enabled(Boolean), teachers(M2M), classes(M2M)`.
- الأكواد المدعومة في المحرك: `max_periods_per_day, max_consecutive, spread_subject,
  max_consecutive_gap, period_repeat, avoid_first_last`.
- التطبيق حسب `scope` + مجموعات المعلمين/الصفوف (انظر 3).

### 2.5 FixedLesson (الحصص المثبتة)
- `plan, day, period, teacher, subject, student_class`.
- مثبّتة بالوقت؛ يجب أن يُجبرها الـ Solver.

### 2.6 ScheduleEntry (مخرجات الجدول)
- `plan, day, period, teacher, subject, student_class, fixed, color`.
- القيود الفريدة الحالية (بعد الترحيل 0038):
  - `unique_plan_teacher_cell` = `(plan, teacher, day, period)` — يمنع تداخل المعلم.
  - `unique_plan_class_cell` = `(plan, student_class, day, period)` — يمنع تداخل الصف.
  - **أُزيل** `unique_plan_cell` (كان يفرض حصة واحدة لكل خانة مدرسة = مسار أحادي خاطئ).
- علاقة عكسية: `plan.entries`.

---

## 3. المحرك الحالي (school/scheduling_engine.py)

### 3.1 البنية
- `generate_schedule(plan, seed, iterations, restarts)`: يبني الخطة عبر عدّة محاولات عشوائية
  (`restarts=12`)، ويُبقي الأفضل حسب `(عدد غير المجدول، hard_score، soft_score)`.
- `_attempt(plan, ...)`: يحاول وضع الحصص ثم يحسّن بصعود تلّي (local swaps).
- `evaluate_plan(plan)`: يقيّم القيود على جدول موجود (يُستخدم للعرض لا للتحقق الصارم).
- `_eff(groups, t, c)`: يحسب القيم الفعّالة لقيد (معلم، صف) مع مراعاة `scope`.

### 3.2 الخوارزمية
1. يبني قائمة حصص (`lessons`) من `TeachingLoad` بعد خصم الحصص المثبتة.
2. يضع الحصص المثبتة أولًا.
3. يرتّب الحصص الأثقل (أكثر معلم/صف مشغول) أولًا.
4. لكل حصة يبحث عن أفضل خانة متاحة (greedy + `slot_cost`).
5. ما لم يُوضع يُضاف إلى `unscheduled` (مع سبب تقريبي).
6. صعود تلّي لتقليل عقوبة قيود المعلم (soft).

### 3.3 المشاكل الجوهرية (لماذا لا يعطي جدولًا صحيحًا)
- **لا يثبت الوجود/عدم الوجود:** إن كانت المسألة مستحيلة، يعيد «جدول ناقص» (بعض الحصص في
  `unscheduled`) ويعتبره ناجحًا جزئيًا بدل `INFEASIBLE` مع تشخيص. هذا بالضبط ما رآه المستخدم
  (27 حصة غير مجدولة دون سبب واضح).
- **سعة الصف معتبرة ضمنيًا لا رياضيًا:** إن كان مجموع حصص صف ما > `أيام×حصص`، المحرك يملأ
  كل خانات الصف ثم يترك الباقي `unscheduled` برسالة «الصف مشغول (تجاوز سعة الصف)» — لكنه لا
  يكتشف الاستحالة قبل التوليد ولا يبلّغ سببًا مثل «الصف 5أ يحتاج 40 وسعة الخطة 35».
- **Greedy لا يضمن الجدول الكامل:** وضع حصة مبكرًا قد يجعل الباقي مستحيلًا رغم وجود حل؛ المحرك
  لا يبحث في فضاء الحلول كاملًا.
- **القيود الصلبة/التفضيلية غير مفصولة حقيقيًا:** `max_periods_per_day` كان يُطبَّق كقيد صلب
  افتراضي (6/يوم) رغم عدم وجود قيد من المستخدم؛ أُزيل مؤخرًا. التقييم عبر `_eff` يعتمد أول صف
  وُجد للمعلم في تقييم قيود النطاق (`t_classes_of`) — وهو تقريب خاطئ لتعدد الشعب (نقطة حرجة في
  المواصفات).
- **لا يوجد ScheduleValidator صارم:** `evaluate_plan` للعرض فقط؛ لا يمنع حفظ جدول فيه خرق.
- **لا يوجد Diagnostics:** عند الفشل لا يفسّر التعارض (مثل FixedLesson يتعارض مع Availability).

### 3.4 القيود المطبّقة حاليًا (عبر `_eff`)
- `max_periods_per_day` (صلب، افتراضيًا None الآن).
- `max_consecutive` (تفضيلي في التكلفة).
- `spread_subject` (تكرار المادة بحد أقصى/يوم).
- `max_consecutive_gap` (أقصى فراغ متتالٍ).
- `period_repeat` (تكرار حصة بحد أيام).
- `avoid_first_last`.

---

## 4. مسار التوليد الحالي (school/views.py → schedule_generate)

- الزر «إنشاء البرنامج» (POST) يستدعي `generate_schedule(plan)`.
- عند النجاح: `ScheduleEntry.objects.filter(plan=plan).delete()` ثم `bulk_create(entries)`.
- يحدّث `hard_score/soft_score/status='active'/generated_at`.
- يعرض رسائل: تحذير بعدد غير المجدول، أو تحذير بتعارض صلب، أو نجاح.
- **لا يوجد طبقة Solver منفصلة ولا Validator ولا Diagnostics.**

---

## 5. المشاكل التي تمنع محركًا صحيحًا (ملخص)

1. الاعتماد على Greedy + Random Restarts + Local Swaps كأساس → لا يضمن الجدول الكامل ولا
   يثبت الاستحالة.
2. الحصص غير المجدولة تُعامل كنجاح جزئي لا كـ `INFEASIBLE`.
3. غياب التشخيص: لا يُبيَّن سبب الاستحالة (سعة صف، تفريغ، حصة مثبتة متعارضة…).
4. تقييم قيود النطاق عبر «أول صف للمعلم» خاطئ لتعدد الشعب.
5. لا يوجد فصل صريح وحقيقي بين Hard (داخل Solver) و Soft (penalty في Objective).
6. لا يوجد Validator مستقل يتحقق من الجدول الناتج قبل الحفظ.
7. المحرك مكتوف داخل views/`scheduling_engine.py` بلا بنية طبقات (solver/constraints/objective/
   validator/diagnostics).

---

## 6. الاستنتاج والتوصية

- البيئة تدعم OR-Tools CP-SAT (مثبّت بنجاح على Python 3.12).
- التوصية: **استبدال نواة التوليد بـ CP-SAT** مع الحفاظ على كل النماذج والواجهات الحالية.
- النموذج الرياضي المقترح (التفصيل في Phase B):
  - متغيرات قرار: `x[lesson_id, day, period]` منطقية.
  - Hard: نصاب exact، لا تداخل معلم، لا تداخل صف، التفريغ، الحصص المثبتة، عدم استخدام يوم/حصة
    غير فعّالة، واحترام `ScheduleConstraint` ذات `type='hard'`.
  - Soft (penalty في Objective): فراغات المعلم، الفراغات بين الحصص، الحصص المتتالية، تكرار
    المادة/اليوم، توازن النصاب، الأولى/الأخيرة غير المرغوبة.
  - إنتاج `INFEASIBLE` + تشخيص عند عدم وجود حل.
- طبقة منفصلة: `school/scheduling/{solver,constraints,objective,validator,diagnostics}.py`
  (لا توضع في View).
- دمج الناتج في زر «إنشاء البرنامج» الحالي مع `transaction.atomic()` وحفظ بعد التحقق.

---

## 7. قائمة الملفات للتعديل/الإضافة (مراحل لاحقة)

- جديد: `school/scheduling/__init__.py`, `solver.py`, `constraints.py`, `objective.py`,
  `validator.py`, `diagnostics.py`.
- تعديل: `school/scheduling_engine.py` (استدعاء الـ Solver بدل Greedy، أو استبداله مع الإبقاء
  على `generate_schedule`/`evaluate_plan` كواجهة توافق).
- تعديل: `school/views.py` (`schedule_generate`) لاستخدام الطبقة الجديدة + عرض الحالة
  (OPTIMAL/FEASIBLE/INFEASIBLE) والتشخيص.
- تعديل: `requirements.txt` (إضافة `ortools`).
- جديد/تعديل: اختبارات في `school/tests_schedule.py` + fixture مدرسة حقيقية.
- توثيق: `docs/scheduling_engine_design.md` (Phase B).
