from school.scheduling import solver as _solver
from school.scheduling.diagnostics import pre_validate
from school.scheduling.validator import validate

generate_schedule_cp = _solver.generate_schedule_cp
ScheduleValidator = validate
ScheduleDiagnostics = pre_validate
