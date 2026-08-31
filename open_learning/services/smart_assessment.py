import random
import re


def _lesson_context(lesson):
    payload = lesson.ai_payload or {}
    return {
        'title': lesson.title.strip(),
        'subject': getattr(lesson.subject, 'name', '') or '',
        'description': lesson.description.strip(),
        'objectives': payload.get('objectives') or [],
        'concepts': payload.get('concepts') or [],
        'evaluation_questions': payload.get('evaluation_questions') or [],
        'explanation': payload.get('explanation') or '',
    }


def _difficulty_label(difficulty):
    return {'easy': 'سهل', 'medium': 'متوسط', 'hard': 'متقدم'}.get(difficulty, 'متوسط')


def _is_multiplication_topic(text):
    normalized = text.replace('×', 'x').replace('*', 'x').lower()
    return any(token in normalized for token in ['الضرب', 'ضرب', 'multiplication', 'multiply'])


def _math_mcqs(count, difficulty):
    if difficulty == 'easy':
        low, high = 2, 6
    elif difficulty == 'hard':
        low, high = 6, 12
    else:
        low, high = 3, 10
    questions = []
    used = set()
    seed = low * 100 + high * 10 + count
    rng = random.Random(seed)
    while len(questions) < count:
        a = rng.randint(low, high)
        b = rng.randint(low, high)
        if (a, b) in used:
            continue
        used.add((a, b))
        correct = a * b
        distractors = {
            max(0, correct - a),
            correct + b,
            correct + rng.choice([-2, -1, 1, 2]),
            a + b,
        }
        distractors.discard(correct)
        options = [str(correct)] + [str(x) for x in list(distractors)[:3]]
        while len(options) < 4:
            candidate = correct + len(options) + 2
            if candidate != correct:
                options.append(str(candidate))
        rng.shuffle(options)
        questions.append({
            'text': f'{a} × {b} = ؟',
            'question_type': 'mcq',
            'options': options,
            'correct_answer': str(correct),
            'points': 1,
        })
    return questions


def _generic_questions(context, count):
    title = context['title']
    concepts = [str(x).strip() for x in context['concepts'] if str(x).strip()]
    eval_questions = [str(x).strip() for x in context['evaluation_questions'] if str(x).strip()]
    objectives = [str(x).strip() for x in context['objectives'] if str(x).strip()]
    pool = eval_questions + objectives
    questions = []

    # Use lesson-specific evaluation questions as short, manually reviewable prompts.
    for prompt in pool:
        if len(questions) >= count:
            break
        questions.append({
            'text': prompt,
            'question_type': 'true_false',
            'options': ['صح', 'خطأ'],
            'correct_answer': 'صح',
            'points': 1,
        })

    # Build concept-recognition MCQs when concepts exist.
    for idx, concept in enumerate(concepts):
        if len(questions) >= count:
            break
        distractors = [c for c in concepts if c != concept][:3]
        while len(distractors) < 3:
            distractors.append(f'مفهوم غير مرتبط {len(distractors) + 1}')
        options = [concept] + distractors[:3]
        questions.append({
            'text': f'أي من الآتي يعد مفهوماً أساسياً في درس «{title}»؟',
            'question_type': 'mcq',
            'options': options,
            'correct_answer': concept,
            'points': 1,
        })

    fallback_stems = [
        f'الفكرة الرئيسة في درس «{title}» مرتبطة مباشرة بموضوع الدرس.',
        f'يمكن تطبيق ما تعلمناه في «{title}» في موقف عملي مناسب.',
        f'فهم المصطلحات الأساسية يساعد على إتقان درس «{title}».',
        f'مراجعة أمثلة الدرس تساعد على تحسين الفهم في «{title}».',
    ]
    i = 0
    while len(questions) < count:
        questions.append({
            'text': fallback_stems[i % len(fallback_stems)],
            'question_type': 'true_false',
            'options': ['صح', 'خطأ'],
            'correct_answer': 'صح',
            'points': 1,
        })
        i += 1
    return questions


def generate_quiz_draft(lesson, count=5, difficulty='medium'):
    count = max(3, min(int(count or 5), 20))
    context = _lesson_context(lesson)
    searchable = ' '.join([context['title'], context['subject'], context['description']])
    if _is_multiplication_topic(searchable):
        questions = _math_mcqs(count, difficulty)
    else:
        questions = _generic_questions(context, count)
    return {
        'title': f'اختبار ذكي - {context["title"]}',
        'instructions': (
            f'اختبار مقترح آلياً بمستوى {_difficulty_label(difficulty)}. '
            'راجع الأسئلة والإجابات قبل نشره للطلاب.'
        ),
        'passing_score': 50,
        'max_attempts': 2,
        'questions': questions,
    }


def generate_assignment_draft(lesson, difficulty='medium'):
    context = _lesson_context(lesson)
    objectives = context['objectives'][:3]
    objective_text = '\n'.join(f'- {x}' for x in objectives) if objectives else '- تلخيص الفكرة الرئيسة وتطبيقها.'
    if _is_multiplication_topic(' '.join([context['title'], context['subject'], context['description']])):
        instructions = (
            'حل 8 مسائل متنوعة من موضوع الضرب، ثم اكتب مسألة لفظية من حياتك اليومية '
            'تستخدم فيها الضرب واكتب خطوات الحل بوضوح.'
        )
    else:
        instructions = (
            f'أنجز مهمة قصيرة حول درس «{context["title"]}»: لخص الفكرة الرئيسة في 5-7 أسطر، '
            'ثم قدم مثالاً أو تطبيقاً من الحياة اليومية، وأجب عن سؤال واحد من أسئلة التقويم الموجودة في الدرس.\n\n'
            f'الأهداف التي ينبغي أن يظهرها الحل:\n{objective_text}'
        )
    return {
        'title': f'واجب ذكي - {context["title"]}',
        'instructions': instructions,
        'points': 10 if difficulty != 'hard' else 15,
    }


def remediation_text(lesson, quiz, percentage):
    concepts = (lesson.ai_payload or {}).get('concepts') or []
    concept_text = '، '.join(str(x) for x in concepts[:3])
    focus = f' وركز على المفاهيم: {concept_text}' if concept_text else ''
    return (
        f'نتيجتك في «{quiz.title}» هي {percentage}%. '
        f'راجع شرح درس «{lesson.title}»{focus}. '
        'بعد المراجعة نفّذ النشاط الإلزامي أو تمريناً تدريبياً، ثم أعد المحاولة إن كانت متاحة.'
    )
