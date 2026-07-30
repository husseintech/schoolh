from django.contrib import admin
from .models import Profile, Student, Note, Teacher, TeacherNote, Class, Subject, Announcement, Agenda, StudentLeave, StudentLevel, ExamAnalysis, Message, UserPermission, LessonLink, StudentLateness, SchoolInfo, Meeting, SupervisorVisit, Notification


admin.site.register(Profile)
admin.site.register(Student)
admin.site.register(Note)
admin.site.register(Teacher)
admin.site.register(TeacherNote)
admin.site.register(Class)
admin.site.register(Subject)
admin.site.register(Announcement)
admin.site.register(Agenda)
admin.site.register(StudentLeave)
admin.site.register(StudentLevel)
admin.site.register(ExamAnalysis)
admin.site.register(Message)
admin.site.register(UserPermission)
admin.site.register(LessonLink)
admin.site.register(StudentLateness)
admin.site.register(SchoolInfo)
admin.site.register(Meeting)
admin.site.register(SupervisorVisit)
admin.site.register(Notification)
