from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, PasswordResetOTP, Role


class PasswordResetOTPTests(TestCase):
    """Integration tests for the email-based OTP password reset flow."""

    def setUp(self):
        self.client = APIClient()
        # Fetch or create the role so we don't clash with data migration fixtures
        self.role, _ = Role.objects.get_or_create(
            code='companyuser',
            defaults={'name': 'Company User'},
        )
        # Build the user manually so we can set role_obj before the first save()
        self.user = User(
            username='testuser',
            email='testuser@example.com',
            role_obj=self.role,
        )
        self.user.set_password('OldPassword123!')
        self.user.save()
        self.request_url = reverse('password-reset-request')
        self.confirm_url = reverse('password-reset-confirm')



    # ── Request OTP ────────────────────────────────────────────────────────────

    def test_request_otp_with_valid_email_creates_otp(self):
        """Posting a valid registered email creates a PasswordResetOTP entry."""
        response = self.client.post(self.request_url, {'email': 'testuser@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        self.assertEqual(PasswordResetOTP.objects.filter(user=self.user, is_used=False).count(), 1)

    def test_request_otp_with_unregistered_email_still_returns_200(self):
        """Unknown emails return 200 silently to prevent user enumeration."""
        response = self.client.post(self.request_url, {'email': 'nobody@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_request_otp_with_invalid_email_format_returns_400(self):
        """Invalid email format should fail serializer validation."""
        response = self.client.post(self.request_url, {'email': 'not-an-email'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_otp_replaces_existing_unused_otp(self):
        """Sending a second request deletes the old unused OTP and creates a new one."""
        self.client.post(self.request_url, {'email': 'testuser@example.com'})
        self.client.post(self.request_url, {'email': 'testuser@example.com'})
        self.assertEqual(PasswordResetOTP.objects.filter(user=self.user).count(), 1)

    # ── Confirm / Reset ────────────────────────────────────────────────────────

    def test_confirm_with_valid_otp_resets_password(self):
        """Valid OTP + matching passwords should update the user's password."""
        otp_obj = PasswordResetOTP.objects.create(user=self.user, otp='123456')
        payload = {
            'email': 'testuser@example.com',
            'otp': '123456',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
        }
        response = self.client.post(self.confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPassword456!'))
        otp_obj.refresh_from_db()
        self.assertTrue(otp_obj.is_used)

    def test_confirm_with_wrong_otp_returns_400(self):
        """Wrong OTP code should return a 400 error."""
        PasswordResetOTP.objects.create(user=self.user, otp='999999')
        payload = {
            'email': 'testuser@example.com',
            'otp': '000000',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
        }
        response = self.client.post(self.confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_with_expired_otp_returns_400(self):
        """OTP older than 10 minutes should be rejected as expired."""
        otp_obj = PasswordResetOTP.objects.create(user=self.user, otp='123456')
        # Manually backdate the OTP's created_at to simulate expiry
        PasswordResetOTP.objects.filter(pk=otp_obj.pk).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )
        payload = {
            'email': 'testuser@example.com',
            'otp': '123456',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
        }
        response = self.client.post(self.confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', str(response.data).lower())

    def test_confirm_with_mismatched_passwords_returns_400(self):
        """Confirm password not matching new password should return 400."""
        PasswordResetOTP.objects.create(user=self.user, otp='123456')
        payload = {
            'email': 'testuser@example.com',
            'otp': '123456',
            'new_password': 'NewPassword456!',
            'confirm_password': 'DifferentPassword789!',
        }
        response = self.client.post(self.confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_with_used_otp_returns_400(self):
        """An already-used OTP should not be accepted again."""
        PasswordResetOTP.objects.create(user=self.user, otp='123456', is_used=True)
        payload = {
            'email': 'testuser@example.com',
            'otp': '123456',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
        }
        response = self.client.post(self.confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_with_unknown_email_returns_400(self):
        """Submitting a confirm request for an unknown email should return 400."""
        payload = {
            'email': 'ghost@example.com',
            'otp': '123456',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
        }
        response = self.client.post(self.confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminDashboardTests(TestCase):
    """Tests for the custom Survio admin dashboard script tag security."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='superuser', defaults={'name': 'Superuser'})
        self.admin_user = User(
            username='admin_test',
            email='admin@example.com',
            role_obj=self.role,
            is_staff=True,
            is_superuser=True,
        )
        self.admin_user.set_password('AdminPassword123!')
        self.admin_user.save()
        self.client.force_login(self.admin_user)

    def test_admin_index_renders_json_script_tags_safely(self):
        """Admin index should use Django json_script tags and render HTTP 200 without raw JSON leaks."""
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="line-datasets-data"')
        self.assertContains(response, 'id="category-labels-data"')
        # Ensure json_script format is used
        self.assertContains(response, 'type="application/json"')

    def test_category_name_html_sanitization(self):
        """Saving a category with script tags strips HTML tags automatically."""
        from accounts.models import Category
        cat = Category(name='<script>alert("xss")</script>')
        cat.save()
        self.assertNotIn('<script>', cat.name)
        self.assertEqual(cat.name, 'alert("xss")')

