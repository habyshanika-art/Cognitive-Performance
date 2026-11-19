/**
 * Cognitive Assessment Scripts
 * Typing, Reaction, Memory, Concentration — with paste rejection,
 * mouse/click tracking, and practice mode support.
 */

var TYPING_PASSAGES = [
    'Cognitive performance monitoring helps detect early changes in mental processing speed and attention.',
    'Regular assessment of typing speed and reaction time provides valuable temporal interaction data.',
    'Young adults benefit from continuous tracking of cognitive metrics through simple digital tasks.',
    'Accurate typing and quick reactions are indicators of healthy cognitive function in daily life.',
    'This system collects interaction data to support research on cognitive changes over time.'
];

/** Parse assessment submit response safely (handles HTML redirects / non-JSON). */
function parseSubmitResponse(r) {
    var ct = (r.headers.get('content-type') || '');
    if (ct.indexOf('application/json') === -1) {
        return r.text().then(function () {
            return {
                ok: false,
                data: {
                    success: false,
                    error: r.status === 403
                        ? 'Consent required. Refresh and accept consent first.'
                        : 'Server returned an unexpected response. Please refresh and try again.'
                }
            };
        });
    }
    return r.json().then(function (data) {
        return { ok: r.ok, data: data || {} };
    }).catch(function () {
        return {
            ok: false,
            data: { success: false, error: 'Could not read server response. Please try again.' }
        };
    });
}

/** Shared mouse / click-interval tracker for assessment pages. */
function createMouseTracker(rootEl) {
    var lastX = null, lastY = null, distance = 0, moveCount = 0;
    var clickTimes = [], clickIntervals = [];
    var target = rootEl || document;

    function onMove(e) {
        var x = e.clientX, y = e.clientY;
        if (lastX !== null) {
            var dx = x - lastX, dy = y - lastY;
            distance += Math.sqrt(dx * dx + dy * dy);
            moveCount++;
        }
        lastX = x;
        lastY = y;
    }

    function onClick() {
        var now = Date.now();
        if (clickTimes.length) {
            clickIntervals.push(now - clickTimes[clickTimes.length - 1]);
        }
        clickTimes.push(now);
    }

    target.addEventListener('mousemove', onMove);
    target.addEventListener('click', onClick);

    return {
        summary: function () {
            var avg = null;
            if (clickIntervals.length) {
                var sum = clickIntervals.reduce(function (a, b) { return a + b; }, 0);
                avg = Math.round(sum / clickIntervals.length);
            }
            return {
                distance_px: Math.round(distance),
                move_count: moveCount,
                click_count: clickTimes.length,
                avg_click_interval_ms: avg,
                click_intervals_ms: clickIntervals.slice(0, 50)
            };
        },
        stop: function () {
            target.removeEventListener('mousemove', onMove);
            target.removeEventListener('click', onClick);
        }
    };
}

function isPracticeMode() {
    return typeof IS_PRACTICE !== 'undefined' && IS_PRACTICE;
}

function initTypingTest() {
    var passageEl = document.getElementById('passageDisplay');
    var inputEl = document.getElementById('typingInput');
    var startBtn = document.getElementById('startTypingBtn');
    var submitBtn = document.getElementById('submitTypingBtn');
    var timerEl = document.getElementById('timerDisplay');
    var wpmEl = document.getElementById('wpmDisplay');
    var accuracyEl = document.getElementById('accuracyDisplay');
    var resultEl = document.getElementById('typingResult');
    var area = document.getElementById('typingTestArea') || document.body;
    var mouse = createMouseTracker(area);

    var passage = TYPING_PASSAGES[Math.floor(Math.random() * TYPING_PASSAGES.length)];
    passageEl.textContent = passage;

    var timer = null;
    var timeLeft = 60;
    var startedAt = null;
    var finished = false;
    var keystrokeCount = 0;
    var pasteDetected = false;

    inputEl.addEventListener('paste', function (e) {
        e.preventDefault();
        pasteDetected = true;
        alert('Pasting is not allowed. Please type the passage.');
    });

    inputEl.addEventListener('keydown', function (e) {
        if (e.key && e.key.length === 1 || e.key === 'Backspace' || e.key === 'Delete') {
            keystrokeCount++;
        }
    });

    function getElapsedSeconds() {
        if (!startedAt) return 1;
        var secs = (Date.now() - startedAt) / 1000;
        return secs > 0 ? secs : 1;
    }

    function calcStats() {
        var typed = inputEl.value;
        var correct = 0;
        var compareLen = Math.min(typed.length, passage.length);
        for (var i = 0; i < compareLen; i++) {
            if (typed[i] === passage[i]) correct++;
        }
        var denom = Math.max(typed.length, 1);
        var accuracy = Math.round((correct / denom) * 100);
        var elapsed = getElapsedSeconds();
        var words = correct / 5;
        var wpm = Math.round((words / elapsed) * 60);
        wpmEl.textContent = wpm;
        accuracyEl.textContent = accuracy;

        if (startedAt && !finished && typed.trim().length >= 5) {
            submitBtn.disabled = false;
            submitBtn.removeAttribute('disabled');
            submitBtn.classList.add('ready-to-submit');
        }

        return {
            wpm: wpm,
            accuracy: accuracy,
            correct: correct,
            typed: typed.length,
            elapsed: elapsed
        };
    }

    inputEl.addEventListener('input', calcStats);

    startBtn.addEventListener('click', function () {
        inputEl.disabled = false;
        inputEl.value = '';
        inputEl.focus();
        timeLeft = 60;
        timerEl.textContent = timeLeft;
        startedAt = Date.now();
        finished = false;
        keystrokeCount = 0;
        pasteDetected = false;
        startBtn.classList.add('d-none');
        submitBtn.classList.remove('d-none');
        submitBtn.disabled = false;
        submitBtn.removeAttribute('disabled');
        submitBtn.classList.add('ready-to-submit');
        resultEl.classList.add('d-none');

        if (timer) clearInterval(timer);
        timer = setInterval(function () {
            timeLeft--;
            timerEl.textContent = Math.max(timeLeft, 0);
            calcStats();
            if (timeLeft <= 0) {
                clearInterval(timer);
                timer = null;
                inputEl.disabled = true;
                finished = true;
                submitBtn.disabled = false;
                submitBtn.removeAttribute('disabled');
            }
        }, 1000);
    });

    submitBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (!startedAt) return;

        var typedText = (inputEl.value || '').trim();
        if (typedText.length < 15) {
            alert('Type at least 15 characters of the passage, then click Submit.');
            return;
        }
        if (pasteDetected) {
            alert('Pasted text was detected. Restart and type manually.');
            return;
        }

        var timeTakenMs = Date.now() - startedAt;
        if (timeTakenMs < 2000 && typedText.length >= 15) {
            alert('That was unrealistically fast. Type the passage carefully, then submit.');
            return;
        }

        if (timer) {
            clearInterval(timer);
            timer = null;
        }
        finished = true;
        inputEl.disabled = true;
        submitBtn.disabled = true;

        var stats = calcStats();
        var finishSecs = Math.max(1, Math.round(timeTakenMs / 1000));
        var exactElapsed = Math.max(0.5, timeTakenMs / 1000);
        var exactWpm = Math.round((stats.correct / 5 / exactElapsed) * 60);
        var score = Math.round(exactWpm * (stats.accuracy / 100));
        var label = exactWpm >= 45 ? 'Good' : (exactWpm >= 28 ? 'Average' : 'Needs Improvement');
        var mouseSummary = mouse.summary();
        mouse.stop();

        fetch(SUBMIT_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_type: 'typing',
                score: score,
                time_taken_ms: timeTakenMs,
                typing_speed_wpm: exactWpm,
                error_rate: 100 - stats.accuracy,
                is_practice: isPracticeMode(),
                raw_events: {
                    passage_length: passage.length,
                    chars_typed: stats.typed,
                    keystroke_count: Math.max(keystrokeCount, stats.typed),
                    paste_detected: pasteDetected,
                    finish_seconds: finishSecs,
                    accuracy: stats.accuracy,
                    mouse: mouseSummary
                }
            })
        })
        .then(parseSubmitResponse)
        .then(function (res) {
            if (res.data.success) {
                var practiceNote = isPracticeMode() ? ' (practice — not counted)' : '';
                resultEl.textContent = 'Saved' + practiceNote + '! Finished in ' + finishSecs + 's — WPM: ' +
                    exactWpm + ', Accuracy: ' + stats.accuracy + '% — ' + label;
                resultEl.classList.remove('d-none');
                setTimeout(function () { window.location.href = REDIRECT_URL; }, 2500);
            } else {
                alert(res.data.error || 'Failed to save results');
                submitBtn.disabled = false;
                submitBtn.removeAttribute('disabled');
                finished = false;
                inputEl.disabled = false;
            }
        })
        .catch(function () {
            alert('Network error. Please try again.');
            submitBtn.disabled = false;
            submitBtn.removeAttribute('disabled');
            finished = false;
            inputEl.disabled = false;
        });
    });
}

function initReactionTest() {
    var box = document.getElementById('reactionBox');
    var message = document.getElementById('reactionMessage');
    var startBtn = document.getElementById('startReactionBtn');
    var timeEl = document.getElementById('reactionTimeDisplay');
    var trialEl = document.getElementById('trialCount');
    var resultEl = document.getElementById('reactionResult');
    var area = document.getElementById('reactionTestArea') || document.body;
    var mouse = createMouseTracker(area);

    var trials = [];
    var state = 'idle';
    var greenTime = null;
    var waitTimeout = null;

    function avgReaction() {
        if (trials.length === 0) return 0;
        var sum = trials.reduce(function (a, b) { return a + b; }, 0);
        return Math.round(sum / trials.length);
    }

    function nextTrial() {
        state = 'waiting';
        box.className = 'reaction-box waiting';
        message.textContent = 'Wait for green...';
        var delay = 600 + Math.random() * 2200;
        waitTimeout = setTimeout(function () {
            state = 'ready';
            greenTime = Date.now();
            box.className = 'reaction-box ready';
            message.textContent = 'Click now!';
        }, delay);
    }

    startBtn.addEventListener('click', function () {
        trials = [];
        trialEl.textContent = '0';
        startBtn.classList.add('d-none');
        resultEl.classList.add('d-none');
        nextTrial();
    });

    box.addEventListener('click', function () {
        if (state === 'idle') return;

        if (state === 'waiting') {
            clearTimeout(waitTimeout);
            state = 'too-soon';
            box.className = 'reaction-box too-soon';
            message.textContent = 'Too soon! Click Start to retry.';
            startBtn.classList.remove('d-none');
            return;
        }

        if (state === 'ready') {
            var rt = Date.now() - greenTime;
            trials.push(rt);
            trialEl.textContent = trials.length;
            timeEl.textContent = rt;
            state = 'idle';
            box.className = 'reaction-box';
            message.textContent = 'Trial ' + trials.length + ': ' + rt + ' ms';

            if (trials.length < 3) {
                setTimeout(nextTrial, 800);
            } else {
                var avg = avgReaction();
                var score = Math.max(0, Math.round(100 - avg / 10));
                var label = avg <= 400 ? 'Good' : (avg <= 600 ? 'Average' : 'Needs Improvement');
                var mouseSummary = mouse.summary();
                mouse.stop();

                fetch(SUBMIT_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        task_type: 'reaction',
                        score: score,
                        time_taken_ms: avg * 3,
                        response_time_ms: avg,
                        error_rate: 0,
                        is_practice: isPracticeMode(),
                        raw_events: { trials: trials, mouse: mouseSummary }
                    })
                })
                .then(parseSubmitResponse)
                .then(function (res) {
                    if (res.data.success) {
                        var practiceNote = isPracticeMode() ? ' (practice — not counted)' : '';
                        resultEl.textContent = 'Saved' + practiceNote + '! Average: ' + avg + ' ms — ' + label +
                            ' (Good ≤ 400 ms · Average ≤ 600 ms)';
                        resultEl.classList.remove('d-none');
                        setTimeout(function () { window.location.href = REDIRECT_URL; }, 2500);
                    } else {
                        alert(res.data.error || 'Failed to save');
                        startBtn.classList.remove('d-none');
                    }
                })
                .catch(function () {
                    alert('Network error. Please try again.');
                    startBtn.classList.remove('d-none');
                });
            }
        }
    });
}

/**
 * Short memory task only: digit-span style sequences.
 * 5 rounds, length increases from 3 → 7.
 */
function initMemoryTest() {
    var displayEl = document.getElementById('memoryDisplay');
    var inputEl = document.getElementById('memoryInput');
    var startBtn = document.getElementById('startMemoryBtn');
    var submitBtn = document.getElementById('submitMemoryBtn');
    var roundEl = document.getElementById('memoryRound');
    var resultEl = document.getElementById('memoryResult');
    var area = document.getElementById('memoryTestArea') || document.body;
    var mouse = createMouseTracker(area);

    var totalRounds = 5;
    var round = 0;
    var levelsCompleted = 0;
    var currentSeq = '';
    var startedAt = null;
    var roundResults = [];

    function randomDigits(len) {
        var s = '';
        for (var i = 0; i < len; i++) {
            s += String(Math.floor(Math.random() * 10));
        }
        return s;
    }

    function showSequence(seq, done) {
        displayEl.textContent = seq;
        displayEl.classList.add('memory-show');
        inputEl.value = '';
        inputEl.disabled = true;
        submitBtn.disabled = true;
        setTimeout(function () {
            displayEl.textContent = 'Enter the digits you saw';
            displayEl.classList.remove('memory-show');
            inputEl.disabled = false;
            inputEl.focus();
            submitBtn.disabled = false;
            if (done) done();
        }, 900 + seq.length * 350);
    }

    function finishTest() {
        var score = Math.round((levelsCompleted / totalRounds) * 100);
        var timeTakenMs = Date.now() - startedAt;
        var mouseSummary = mouse.summary();
        mouse.stop();
        var label = score >= 70 ? 'Good' : (score >= 45 ? 'Average' : 'Needs Improvement');

        fetch(SUBMIT_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_type: 'memory',
                score: score,
                memory_score: score,
                time_taken_ms: timeTakenMs,
                error_rate: 100 - score,
                is_practice: isPracticeMode(),
                raw_events: {
                    levels_completed: levelsCompleted,
                    total_rounds: totalRounds,
                    rounds: roundResults,
                    mouse: mouseSummary
                }
            })
        })
        .then(parseSubmitResponse)
        .then(function (res) {
            if (res.data.success) {
                var practiceNote = isPracticeMode() ? ' (practice — not counted)' : '';
                resultEl.textContent = 'Saved' + practiceNote + '! Memory score: ' + score +
                    '/100 (' + levelsCompleted + '/' + totalRounds + ' correct) — ' + label;
                resultEl.classList.remove('d-none');
                setTimeout(function () { window.location.href = REDIRECT_URL; }, 2500);
            } else {
                alert(res.data.error || 'Failed to save');
                startBtn.classList.remove('d-none');
            }
        })
        .catch(function () {
            alert('Network error. Please try again.');
            startBtn.classList.remove('d-none');
        });
    }

    function nextRound() {
        round++;
        if (round > totalRounds) {
            finishTest();
            return;
        }
        roundEl.textContent = round + ' / ' + totalRounds;
        var len = 2 + round; // 3..7
        currentSeq = randomDigits(len);
        showSequence(currentSeq);
    }

    startBtn.addEventListener('click', function () {
        round = 0;
        levelsCompleted = 0;
        roundResults = [];
        startedAt = Date.now();
        startBtn.classList.add('d-none');
        submitBtn.classList.remove('d-none');
        resultEl.classList.add('d-none');
        nextRound();
    });

    submitBtn.addEventListener('click', function () {
        if (!startedAt || inputEl.disabled) return;
        var answer = (inputEl.value || '').replace(/\s+/g, '');
        var correct = answer === currentSeq;
        if (correct) levelsCompleted++;
        roundResults.push({
            round: round,
            length: currentSeq.length,
            correct: correct
        });
        inputEl.disabled = true;
        submitBtn.disabled = true;
        displayEl.textContent = correct ? 'Correct!' : ('Shown: ' + currentSeq);
        setTimeout(nextRound, 700);
    });
}

/**
 * Concentration task: go/no-go sustained attention.
 * Click only when letter X appears among distractors.
 */
function initConcentrationTest() {
    var displayEl = document.getElementById('concentrationDisplay');
    var startBtn = document.getElementById('startConcentrationBtn');
    var clickBtn = document.getElementById('clickConcentrationBtn');
    var trialEl = document.getElementById('concTrial');
    var hitsEl = document.getElementById('concHits');
    var falseEl = document.getElementById('concFalse');
    var resultEl = document.getElementById('concentrationResult');
    var area = document.getElementById('concentrationTestArea') || document.body;
    var mouse = createMouseTracker(area);

    var TOTAL = 30;
    var LETTERS = 'ABCDEFGHJKLMNPQRSTUVWYZ'; // no X in distractors
    var trial = 0;
    var hits = 0;
    var misses = 0;
    var falseAlarms = 0;
    var targetsShown = 0;
    var currentIsTarget = false;
    var responded = false;
    var startedAt = null;
    var timer = null;
    var running = false;

    function showNext() {
        if (trial >= TOTAL) {
            finish();
            return;
        }
        trial++;
        trialEl.textContent = trial;
        responded = false;
        // ~30% targets, but guarantee at least 5 targets over TOTAL trials
        var remaining = TOTAL - trial + 1;
        var need = Math.max(0, 5 - targetsShown);
        if (need >= remaining) {
            currentIsTarget = true;
        } else {
            currentIsTarget = Math.random() < 0.3;
        }
        var letter;
        if (currentIsTarget) {
            letter = 'X';
            targetsShown++;
        } else {
            letter = LETTERS.charAt(Math.floor(Math.random() * LETTERS.length));
        }
        displayEl.textContent = letter;
        displayEl.style.color = currentIsTarget ? '#c62828' : '#1565c0';

        if (timer) clearTimeout(timer);
        timer = setTimeout(function () {
            if (!responded && currentIsTarget) {
                misses++;
            }
            showNext();
        }, 900);
    }

    function finish() {
        running = false;
        clickBtn.disabled = true;
        clickBtn.classList.add('d-none');
        if (timer) clearTimeout(timer);
        displayEl.textContent = 'Done';
        displayEl.style.color = '';

        // Score: reward hits, penalise misses and false alarms
        var hitRate = targetsShown ? (hits / targetsShown) : 0;
        var falsePenalty = Math.min(falseAlarms * 4, 40);
        var score = Math.max(0, Math.round(hitRate * 100 - falsePenalty));
        var timeTakenMs = Date.now() - startedAt;
        var mouseSummary = mouse.summary();
        mouse.stop();
        var label = score >= 75 ? 'Good' : (score >= 50 ? 'Average' : 'Needs Improvement');

        fetch(SUBMIT_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_type: 'concentration',
                score: score,
                concentration_score: score,
                time_taken_ms: timeTakenMs,
                error_rate: Math.max(0, 100 - score),
                is_practice: isPracticeMode(),
                raw_events: {
                    total_trials: TOTAL,
                    targets_shown: targetsShown,
                    hits: hits,
                    misses: misses,
                    false_alarms: falseAlarms,
                    mouse: mouseSummary
                }
            })
        })
        .then(parseSubmitResponse)
        .then(function (res) {
            if (res.data.success) {
                var practiceNote = isPracticeMode() ? ' (practice — not counted)' : '';
                resultEl.textContent = 'Saved' + practiceNote + '! Concentration: ' + score +
                    '/100 (hits ' + hits + '/' + targetsShown + ', false ' + falseAlarms + ') — ' + label;
                resultEl.classList.remove('d-none');
                setTimeout(function () { window.location.href = REDIRECT_URL; }, 2500);
            } else {
                alert(res.data.error || 'Failed to save');
                startBtn.classList.remove('d-none');
            }
        })
        .catch(function () {
            alert('Network error. Please try again.');
            startBtn.classList.remove('d-none');
        });
    }

    startBtn.addEventListener('click', function () {
        trial = 0;
        hits = 0;
        misses = 0;
        falseAlarms = 0;
        targetsShown = 0;
        startedAt = Date.now();
        running = true;
        startBtn.classList.add('d-none');
        clickBtn.classList.remove('d-none');
        clickBtn.disabled = false;
        hitsEl.textContent = '0';
        falseEl.textContent = '0';
        resultEl.classList.add('d-none');
        showNext();
    });

    clickBtn.addEventListener('click', function () {
        if (!running || responded) return;
        responded = true;
        if (currentIsTarget) {
            hits++;
            hitsEl.textContent = hits;
        } else {
            falseAlarms++;
            falseEl.textContent = falseAlarms;
        }
    });
}
