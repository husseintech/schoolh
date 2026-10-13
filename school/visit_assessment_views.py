from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from .models import VisitAssessmentReport, Teacher, SchoolInfo, has_perm
from .views import current_teacher_scope

INDICATORS=[
('التخطيط وصياغة النتاجات','يحدد المعلم نتاجات تعلم واضحة ومحددة وقابلة للملاحظة والقياس.'),
('اختيار وموثوقية المصدر','يختار مصدراً مفتوحاً موثوقاً وآمناً ومناسباً لعمر الطلبة ومستواهم.'),
('حقوق الملكية الفكرية','يلتزم بالترخيص المفتوح وينسب المصدر إلى صاحبه الأصلي.'),
('التجهيز التقني المسبق','يجهز المصادر الرقمية مسبقاً لتفادي المعوقات التقنية.'),
('القيمة التعليمية المضافة','يوظف المصدر في البحث والتحليل والتطبيق لا المشاهدة السلبية فقط.'),
('التسلسل البنائي للدرس','يتسلسل الدرس من التهيئة والاستكشاف إلى التطبيق والتقويم.'),
('استراتيجيات التعلم النشط','يوظف استراتيجيات تعلم نشط فردية وثنائية وجماعية.'),
('ربط التعلم بالواقع والمهارات','يربط المحتوى بواقع الطلبة ويدعم مهارات القراءة والحساب.'),
('فاعلية الطالب وإنتاج المعرفة','يجعل الطالب مشاركاً فاعلاً ومنتجاً للمعرفة.'),
('مهارات التفكير العليا','يطرح أسئلة تستثير التحليل والتركيب والتقييم.'),
('الحوار والتعبير السليم','يتيح فرصاً للحوار والتعبير عن الأفكار بلغة سليمة.'),
('المواطنة الرقمية والقيم','يعزز السلوك الإيجابي والمواطنة الرقمية الآمنة.'),
('مراعاة الفروق الفردية','يكيف الأنشطة لتلبية الاحتياجات والمستويات المختلفة.'),
('التوظيف المسؤول للتقنية والذكاء الاصطناعي','يوظف التقنية بمسؤولية ويحافظ على خصوصية الطلبة.'),
('امتداد واستدامة التعلم','يوفر فرصاً لاستمرار التعلم خارج الحصة.'),
('التقويم التكويني المستمر','يستخدم أدوات متنوعة للتحقق من الفهم واكتشاف فجوات التعلم.'),
('شفافية معايير التقييم','يوضح معايير التقييم قبل تنفيذ المهمة.'),
('التغذية الراجعة البناءة','يقدم تغذية راجعة فورية ومحددة تساعد الطالب على التطور.'),
('الإدارة الصفية واستثمار الوقت','يدير الصف وينظم الانتقال بين الأنشطة لاستثمار الوقت.'),
('الأثر التعليمي وتحقيق النتاجات','يتحقق من أثر التعلم ومدى تحقيق النتاجات المستهدفة.')]

def ctx(report,form_mode=False):
 return {'report':report,'info':SchoolInfo.objects.first(),'indicators':INDICATORS,'today':date.today(),'form_mode':form_mode,'report_type_label':report.get_report_type_display(),'saved_reports':VisitAssessmentReport.objects.filter(teacher=report.teacher).order_by('-visit_date','-updated_at')}

def teacher_scope(request,teacher_id):
 scoped=current_teacher_scope(request.user)
 if scoped and scoped.id!=teacher_id:return None
 return scoped or get_object_or_404(Teacher,pk=teacher_id)

def save_report(request,report,teacher,kind):
 report.teacher=teacher; report.report_type=kind
 report.visit_date=request.POST.get('visit_date') or date.today()
 for field in ['visit_number','subject_area','lesson_topic','class_name','section']:
  setattr(report,field,request.POST.get(field,'').strip())
 if kind=='primary':
  report.scores={str(i):request.POST.get(f'score_{i}','') for i in range(1,21)}
  report.evidence={str(i):request.POST.get(f'evidence_{i}','').strip() for i in range(1,21)}
  keys=['source_name','lesson_objectives','strengths','improvement_areas','recommendations','general_judgement','diagnosis']
 else:
  report.scores={};report.evidence={}
  keys=['content_teaching','teaching_strategies','evaluation_strategies','other_matters','plans_followup','attendance_followup','committees_followup','violence_policy','recommendations','principal_sign_date','teacher_receipt_date','additional_notes']
 report.details={k:request.POST.get(k,'').strip() for k in keys}
 if not report.created_by_id:report.created_by=request.user
 report.save();messages.success(request,'تم حفظ التقرير ويمكن تعديله لاحقاً.')
 return redirect('visit_assessment_report',report_id=report.id)

@login_required
def visit_assessment_form(request,report_type,teacher_id):
 if report_type not in ('primary','upper') or not has_perm(request.user,'inspection_visits','view') or not has_perm(request.user,'inspection_visits','add'):
  messages.error(request,'لا توجد صلاحية أو أن نوع التقرير غير صحيح.');return redirect('visit_program_list')
 teacher=teacher_scope(request,teacher_id)
 if teacher is None:messages.error(request,'لا يمكنك الوصول إلى سجل هذا المعلم.');return redirect('dashboard')
 report=VisitAssessmentReport(teacher=teacher,report_type=report_type,visit_date=date.today())
 if request.method=='POST':return save_report(request,report,teacher,report_type)
 return render(request,'school/visit_assessment_form.html',ctx(report,True))

@login_required
def visit_assessment_edit(request,report_id):
 report=get_object_or_404(VisitAssessmentReport.objects.select_related('teacher'),pk=report_id)
 scoped=current_teacher_scope(request.user)
 if (scoped and scoped.id!=report.teacher_id) or not has_perm(request.user,'inspection_visits','edit'):
  messages.error(request,'ليس لديك صلاحية تعديل هذا التقرير.');return redirect('dashboard')
 if request.method=='POST':return save_report(request,report,report.teacher,report.report_type)
 return render(request,'school/visit_assessment_form.html',ctx(report,True))

@login_required
def visit_assessment_report(request,report_id):
 report=get_object_or_404(VisitAssessmentReport.objects.select_related('teacher'),pk=report_id)
 scoped=current_teacher_scope(request.user)
 if (scoped and scoped.id!=report.teacher_id) or (not has_perm(request.user,'inspection_visits','view') and not scoped):
  messages.error(request,'ليس لديك صلاحية عرض التقرير.');return redirect('dashboard')
 return render(request,'school/visit_assessment_report.html',ctx(report))

@login_required
def visit_assessment_word(request,report_id):
 report=get_object_or_404(VisitAssessmentReport.objects.select_related('teacher'),pk=report_id)
 scoped=current_teacher_scope(request.user)
 if (scoped and scoped.id!=report.teacher_id) or (not has_perm(request.user,'inspection_visits','view') and not scoped):
  messages.error(request,'ليس لديك صلاحية تنزيل التقرير.');return redirect('dashboard')
 html=render_to_string('school/visit_assessment_document.html',ctx(report),request=request)
 response=HttpResponse(html,content_type='application/msword; charset=utf-8')
 response['Content-Disposition']=f'attachment; filename="visit-assessment-{report.id}.doc"'
 return response
