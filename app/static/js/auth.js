/**
 * Authentication Page Scripts
 * Password toggle, strength meter, profile picture preview.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Show / hide password
    document.querySelectorAll('.password-toggle').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var targetId = btn.getAttribute('data-target');
            var input = document.getElementById(targetId);
            if (!input) return;

            var icon = btn.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.replace('bi-eye', 'bi-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.replace('bi-eye-slash', 'bi-eye');
            }
        });
    });

    // Password strength meter (register page)
    var pwInput = document.getElementById('password');
    var strengthEl = document.getElementById('passwordStrength');
    if (pwInput && strengthEl) {
        pwInput.addEventListener('input', function () {
            var val = pwInput.value;
            var score = 0;
            if (val.length >= 8) score++;
            if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score++;
            if (/[0-9]/.test(val)) score++;
            if (/[^A-Za-z0-9]/.test(val)) score++;

            strengthEl.className = 'password-strength';
            var textEl = strengthEl.querySelector('.strength-text');

            if (!val) {
                textEl.textContent = 'Password strength';
            } else if (score <= 1) {
                strengthEl.classList.add('strength-weak');
                textEl.textContent = 'Weak — add numbers & symbols';
            } else if (score <= 2) {
                strengthEl.classList.add('strength-fair');
                textEl.textContent = 'Fair — almost there';
            } else {
                strengthEl.classList.add('strength-strong');
                textEl.textContent = 'Strong password';
            }
        });
    }

    // Profile picture preview (register page)
    var fileInput = document.getElementById('profile_picture');
    var preview = document.getElementById('avatarPreview');
    if (fileInput && preview) {
        fileInput.addEventListener('change', function () {
            var file = fileInput.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function (e) {
                preview.innerHTML = '<img src="' + e.target.result + '" alt="Preview">';
            };
            reader.readAsDataURL(file);
        });
    }
});
