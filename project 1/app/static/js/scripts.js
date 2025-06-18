// document.addEventListener('DOMContentLoaded', () => {
//     const videoInput = document.querySelector('input[type="file"][accept="video/*"]');
//     if (videoInput) {
//         videoInput.addEventListener('change', (e) => {
//             const file = e.target.files[0];
//             if (file) {
//                 const video = document.createElement('video');
//                 video.src = URL.createObjectURL(file);
//                 video.onloadedmetadata = () => {
//                     if (video.duration > 1200) {  // 20 minutes in seconds
//                         alert('Video must be 20 minutes or less.');
//                         e.target.value = '';
//                     }
//                 };
//             }
//         });
//     }

    const profilePicInput = document.querySelector('input[name="profile_picture"]');
    if (profilePicInput) {
        profilePicInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file && file.size > 2 * 1024 * 1024) {
                alert('Profile picture must be under 2MB.');
                e.target.value = '';
            }
        });
    }

    const iconLinks = document.querySelectorAll('.icon-link');
    iconLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const postId = link.getAttribute('data-post-id');
            const action = link.getAttribute('data-action');
            const icon = link.querySelector('i');

            icon.classList.add('animate-scale');
            setTimeout(() => icon.classList.remove('animate-scale'), 300);

            if (postId && (action === 'like' || action === 'dislike')) {
                fetch(`/like/${postId}/${action}`, {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                }).then(response => {
                    if (response.ok) {
                        response.json().then(data => {
                            const likeCount = link.querySelector('.like-count');
                            const dislikeCount = link.querySelector('.dislike-count');
                            if (likeCount) likeCount.textContent = data.likes;
                            if (dislikeCount) dislikeCount.textContent = data.dislikes;
                            if (action === 'like') {
                                icon.classList.toggle('fas');
                                icon.classList.toggle('far');
                                icon.classList.add('animate-fade');
                                setTimeout(() => icon.classList.remove('animate-fade'), 500);
                            }
                        });
                    }
                });
            } else if (action === 'follow' || action === 'unfollow') {
                fetch(link.getAttribute('href'), {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                }).then(response => {
                    if (response.ok) {
                        const isFollowing = action === 'follow';
                        link.setAttribute('data-action', isFollowing ? 'unfollow' : 'follow');
                        link.setAttribute('href', isFollowing ? `/unfollow/${link.getAttribute('data-user-id')}` : `/follow/${link.getAttribute('data-user-id')}`);
                        link.innerHTML = isFollowing ? `<i class="fas fa-user-minus"></i> Unfollow` : `<i class="fas fa-user-plus"></i> Follow`;
                        icon.classList.add('animate-fade');
                        setTimeout(() => icon.classList.remove('animate-fade'), 500);
                    }
                });
            } else if (action === 'message' || action === 'edit') {
                window.location.href = link.getAttribute('href');
            }
        });
    });

    // New code: handle comment form submission asynchronously
    const commentForm = document.querySelector('.comment-form');
    if (commentForm) {
        commentForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(commentForm);
            const postId = commentForm.closest('.form-container').querySelector('.btn.btn-like').getAttribute('data-post-id');
            fetch(`/post/${postId}`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then(response => {
                if (response.ok) {
                    response.json().then(data => {
                        // Clear textarea
                        commentForm.querySelector('textarea[name="content"]').value = '';
                        // Update comments section
                        const commentsSection = document.querySelector('.comments-section');
                        if (commentsSection) {
                            // Append new comment
                            const newComment = document.createElement('div');
                            newComment.classList.add('comment-box');
                            newComment.innerHTML = `
                                <div class="comment-content-wrapper">
                                    <img src="${data.author_profile_picture}" alt="Profile" class="profile-pic-small">
                                    <a href="/profile/${data.author_id}">${data.author_username}</a>: ${data.content}
                                </div>
                                <span class="comment-date">${data.date_posted}</span>
                            `;
                            commentsSection.appendChild(newComment);
                        }
                    });
                } else {
                    alert('Failed to add comment.');
                }
            }).catch(() => {
                alert('Error submitting comment.');
            });
        });
    }
});
