from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Judgment, ActionPlan, OfficerReview
from .utils.extractor import extract_text_from_pdf
from .utils.groq_service import extract_action_plan


def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials')
    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def upload_judgment(request):
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf')
        if not pdf_file:
            messages.error(request, 'Please select a PDF file')
            return render(request, 'core/upload.html')

        # Save judgment record
        judgment = Judgment.objects.create(
            uploaded_by=request.user,
            uploaded_pdf=pdf_file
        )

        # Extract text from PDF
        text = extract_text_from_pdf(judgment.uploaded_pdf.path)

        if not text:
            messages.error(request, 'Could not extract text from PDF. Please try another file.')
            judgment.delete()
            return render(request, 'core/upload.html')

        judgment.raw_text = text
        judgment.save()

        # Send text to Gemini for extraction
        data = extract_action_plan(text)

        # Save the generated action plan
        ActionPlan.objects.create(
            judgment=judgment,
            case_number=data.get('case_number', ''),
            court_name=data.get('court_name', ''),
            judgment_date=data.get('judgment_date') or '',
            parties=data.get('parties', ''),
            judgment_summary=data.get('judgment_summary', ''),
            directives=data.get('directives', []),
            compliance_deadline=data.get('compliance_deadline') or '',
            appeal_recommended=True if str(data.get('appeal_recommended')).lower() == 'true' else False,
            appeal_reason=data.get('appeal_reason', '')
        )

        judgment.case_number = data.get('case_number', f'Case-{judgment.id}')
        judgment.save()

        messages.success(request, 'Judgment processed successfully. Please review the action plan.')
        return redirect('review_plan', pk=judgment.pk)

    return render(request, 'core/upload.html')


@login_required
def review_plan(request, pk):
    judgment = get_object_or_404(Judgment, pk=pk)
    plan = judgment.action_plan

    # Block reviewing already decided plans
    if judgment.status != 'pending':
        messages.info(request, 'This plan has already been reviewed.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Officer can edit any field before approving
        plan.case_number = request.POST.get('case_number', plan.case_number)
        plan.court_name = request.POST.get('court_name', plan.court_name)
        plan.judgment_summary = request.POST.get('judgment_summary', plan.judgment_summary)
        plan.compliance_deadline = request.POST.get('compliance_deadline', plan.compliance_deadline)
        plan.appeal_recommended = request.POST.get('appeal_recommended') == 'on'
        plan.appeal_reason = request.POST.get('appeal_reason', plan.appeal_reason)
        plan.save()

        decision = request.POST.get('decision')
        approved = decision == 'approve'

        OfficerReview.objects.create(
            action_plan=plan,
            reviewed_by=request.user,
            approved=approved,
            notes=request.POST.get('notes', '')
        )

        judgment.status = 'approved' if approved else 'rejected'
        judgment.save()

        msg = 'Action plan approved and published to dashboard.' if approved else 'Plan rejected.'
        messages.success(request, msg)
        return redirect('dashboard')

    return render(request, 'core/review.html', {'judgment': judgment, 'plan': plan})


@login_required
def dashboard(request):
    approved = Judgment.objects.filter(
        status='approved'
    ).select_related('action_plan').order_by('-uploaded_at')

    pending = Judgment.objects.filter(
        status='pending'
    ).select_related('action_plan').order_by('-uploaded_at')

    rejected = Judgment.objects.filter(
        status='rejected'
    ).select_related('action_plan').order_by('-uploaded_at')

    return render(request, 'core/dashboard.html', {
        'approved': approved,
        'pending': pending,
        'rejected': rejected
    })