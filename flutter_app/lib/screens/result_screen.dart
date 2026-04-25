import 'package:flutter/material.dart';

class ResultScreen extends StatelessWidget {
  final Map<String, dynamic> data;
  const ResultScreen({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    final result      = (data['result'] as Map<String, dynamic>?) ?? {};
    final ocr         = data['ocr']    as Map<String, dynamic>?;
    final input       = data['input']  as Map<String, dynamic>?;
    final expiryCheck = (result['expiry_check'] as Map<String, dynamic>?) ?? {};

    final status        = result['status']       as String? ?? 'UNKNOWN';
    final message       = result['message']      as String? ?? '';
    final matchScore    = result['match_score']  as int?    ?? 0;
    final isExpired     = result['is_expired']   as bool?   ?? false;
    final batchMatched  = result['batch_matched'];
    final batchNote     = result['batch_match_note'] as String?;
    final expiryMatchDb = expiryCheck['matches_db'];
    final mismatchNote  = expiryCheck['mismatch_note'] as String?;
    final alerts        = (result['alerts'] as List?)?.map((e) => e.toString()).toList() ?? [];

    final th = _theme(status);

    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1565C0),
        foregroundColor: Colors.white,
        title: const Text('Detection Result',
            style: TextStyle(fontWeight: FontWeight.bold)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () =>
              Navigator.of(context).popUntil((r) => r.isFirst),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(children: [

          // ── OCR EXTRACTED DATA ───────────────────────────
          if (ocr != null) ...[
            _Section(
              icon: Icons.document_scanner,
              title: 'Extracted from Image',
              rows: [
                _InfoRow('Medicine name', ocr['medicine_name']),
                _InfoRow('Batch no.',     ocr['batch']),
                _InfoRow('Mfg. date',     ocr['mfg_date']),
                _InfoRow('Exp. date',     ocr['exp_date']),
                _InfoRow('Manufacturer',  ocr['manufacturer']),
                _InfoRow('Words found',   ocr['word_count']?.toString()),
              ],
            ),
            const SizedBox(height: 12),
          ],

          // ── MANUAL INPUT ─────────────────────────────────
          if (input != null) ...[
            _Section(
              icon: Icons.search,
              title: 'Your Search',
              rows: [
                _InfoRow('Drug name', input['drug_name']),
                _InfoRow('Batch no.', input['batch_no']),
                _InfoRow('Exp. date', input['exp_date']),
              ],
            ),
            const SizedBox(height: 12),
          ],

          // ── STATUS BANNER ────────────────────────────────
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: th.bg,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: th.accent.withOpacity(0.45), width: 2),
            ),
            child: Column(children: [
              Icon(th.icon, size: 64, color: th.accent),
              const SizedBox(height: 10),
              Text(th.label,
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold,
                      color: th.accent)),
              const SizedBox(height: 10),
              Text(message,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13,
                      color: th.accent.withOpacity(0.85), height: 1.55)),
              if (matchScore > 0 && batchMatched != true) ...[
                const SizedBox(height: 12),
                Text('Name match: $matchScore%',
                    style: TextStyle(fontSize: 12,
                        color: th.accent.withOpacity(0.7))),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: matchScore / 100, minHeight: 7,
                    backgroundColor: th.accent.withOpacity(0.2),
                    valueColor: AlwaysStoppedAnimation<Color>(th.accent),
                  ),
                ),
              ],
            ]),
          ),
          const SizedBox(height: 16),

          // ── CROSS-CHECK SUMMARY ──────────────────────────
          _CrossCheckCard(
            nameScore:       matchScore,
            batchMatched:    batchMatched,
            isExpired:       isExpired,
            expiryMatchesDb: expiryMatchDb,
          ),
          const SizedBox(height: 14),

          // ── BATCH ALERT (most prominent if batch matched) ─
          if (batchNote != null) ...[
            const SizedBox(height: 12),
            _AlertBanner(
              icon: batchMatched == true
                  ? Icons.dangerous_rounded
                  : Icons.check_circle_outline,
              color: batchMatched == true ? Colors.red[700]! : Colors.green[700]!,
              bgColor: batchMatched == true
                  ? const Color(0xFFFFEBEE)
                  : const Color(0xFFE8F5E9),
              title: batchMatched == true
                  ? '🚨 Batch Number — NSQ Match Found!'
                  : '✅ Batch Number — Not in NSQ List (Safe)',
              body: batchNote,
            ),
          ],
          
          // ── NAME MATCH NOTIFICATION (If batch safe but name might match or is missing) ─
          if (batchMatched != true) ...[
              for (final alert in alerts)
                 if (alert.toLowerCase().contains("name"))
                    Padding(
                        padding: const EdgeInsets.only(top: 12.0),
                        child: _AlertBanner(
                          icon: Icons.info_outline,
                          color: Colors.orange[800]!,
                          bgColor: const Color(0xFFFFF8E1),
                          title: 'Name Notification',
                          body: alert,
                        ),
                    ),
          ],
          
          // ── OTHER ALERTS ──
          for (final alert in alerts)
            if (batchMatched == true && alert.toLowerCase().contains("name mismatch"))
                Padding(
                   padding: const EdgeInsets.only(top: 12.0),
                   child: _AlertBanner(
                     icon: Icons.warning_amber_rounded,
                     color: Colors.orange[800]!,
                     bgColor: const Color(0xFFFFF8E1),
                     title: 'Name Mismatch',
                     body: alert,
                   ),
                ),

          // ── EXPIRY CROSS-CHECK ────────────────────────────
          if (expiryCheck['user_expiry'] != null &&
              expiryCheck['db_expiry'] != null) ...[
            const SizedBox(height: 12),
            _Section(
              icon: Icons.compare_arrows,
              title: 'Expiry Date Cross-Check',
              rows: [
                _InfoRow('Your expiry date', expiryCheck['user_expiry']),
                _InfoRow('Expiry in NSQ DB', expiryCheck['db_expiry']),
                _InfoRow('Dates match?',
                    expiryMatchDb == true  ? '✅ Yes — dates match'
                    : expiryMatchDb == false ? '⚠️ No — dates differ'
                    : 'Could not compare'),
              ],
            ),
          ],

          if (mismatchNote != null) ...[
            const SizedBox(height: 12),
            _AlertBanner(
              icon: Icons.warning_amber_rounded,
              color: Colors.orange[800]!,
              bgColor: const Color(0xFFFFF8E1),
              title: 'Expiry Date Mismatch — Possible Counterfeit',
              body: mismatchNote,
            ),
          ],

          // ── MATCHING DRUG NAMES SUMMARY ───────────────
          if (result['matched_db_records'] != null && (result['matched_db_records'] as List).isNotEmpty) ...[
            const SizedBox(height: 12),
            _Section(
              icon: Icons.list_alt_rounded,
              title: 'Matching Drug Names',
              rows: (result['matched_db_records'] as List).take(8).map((d) {
                return _InfoRow(
                  '${(d as Map)['match_score']}% Match',
                  d['matched_name']
                );
              }).toList(),
            ),
          ],

          // ── NSQ DB RECORDS (TOP 8 DETAILS) ──────────────
          if (result['matched_db_records'] != null && (result['matched_db_records'] as List).isNotEmpty) ...[
            const SizedBox(height: 12),
            if ((result['matched_db_records'] as List).length > 8)
              Padding(
                padding: const EdgeInsets.only(bottom: 8.0, left: 4.0),
                child: Text(
                  'Showing top 8 of ${(result['matched_db_records'] as List).length} possible matches',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.blue[800]),
                ),
              ),
            for (int i = 0; i < (result['matched_db_records'] as List).take(8).length; i++) ...[
              if (i > 0) const SizedBox(height: 12),
              Builder(builder: (context) {
                final rec = result['matched_db_records'][i] as Map<String, dynamic>;
                return _Section(
                  icon: Icons.manage_search,
                  title: 'NSQ Database Record Details ${i + 1}',
                  rows: [
                    _InfoRow('Drug name',    rec['matched_name']),
                    if (rec['match_score'] != null) 
                        _InfoRow('Match confidence', '${rec['match_score']}%'),
                    _InfoRow('Batch in DB',  rec['batch_in_db']),
                    _InfoRow('Mfg. date',    rec['mfg_in_db']),
                    _InfoRow('Expiry (DB)',  rec['db_expiry']),
                    _InfoRow('Manufacturer', rec['manufacturer']),
                    _InfoRow('NSQ reason',   rec['nsq_reason']),
                    _InfoRow('Lab',          rec['lab']),
                    _InfoRow('Alert month',  rec['alert_month']),
                  ],
                );
              }),
            ],
          ] else if (result['matched_name'] != null || result['batch_in_db'] != null) ...[
            const SizedBox(height: 12),
            _Section(
              icon: Icons.manage_search,
              title: 'NSQ Database Record',
              rows: [
                _InfoRow('Drug name',    result['matched_name']),
                _InfoRow('Batch in DB',  result['batch_in_db']),
                _InfoRow('Mfg. date',    result['mfg_in_db']),
                _InfoRow('Expiry (DB)',  result['db_expiry']),
                _InfoRow('Manufacturer', result['manufacturer']),
                _InfoRow('NSQ reason',   result['nsq_reason']),
                _InfoRow('Lab',          result['lab']),
                _InfoRow('Alert month',  result['alert_month']),
              ],
            ),
          ],

          // ── EXPIRED WARNING ───────────────────────────────
          if (isExpired) ...[
            const SizedBox(height: 12),
            _AlertBanner(
              icon: Icons.timer_off,
              color: Colors.orange[800]!,
              bgColor: const Color(0xFFFFF8E1),
              title: 'Medicine is Expired',
              body: 'The expiry date on this package has passed. '
                  'Never consume expired medicines.',
            ),
          ],

          const SizedBox(height: 14),
          // ── DISCLAIMER ───────────────────────────────────
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(13),
            decoration: BoxDecoration(
              color: Colors.grey[100],
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              '⚠️ This app checks CDSCO NSQ alerts. Always consult a licensed '
              'pharmacist or doctor before making medication decisions.',
              style: TextStyle(fontSize: 12, color: Colors.grey[600], height: 1.5),
            ),
          ),
          const SizedBox(height: 16),

          // ── BUTTONS ───────────────────────────────────────
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
                icon: const Icon(Icons.home),
                label: const Text('Home'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 13),
                  side: const BorderSide(color: Color(0xFF1565C0)),
                  foregroundColor: const Color(0xFF1565C0),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.camera_alt),
                label: const Text('Scan Again'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1565C0),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 13),
                ),
              ),
            ),
          ]),
          const SizedBox(height: 16),
        ]),
      ),
    );
  }

  _StatusTheme _theme(String s) {
    switch (s) {
      case 'NSQ':
        return _StatusTheme(bg: const Color(0xFFFFEBEE),
            accent: Colors.red[700]!, icon: Icons.dangerous_rounded,
            label: '⚠️ NOT SAFE — NSQ Drug');
      case 'EXPIRED':
        return _StatusTheme(bg: const Color(0xFFFFF8E1),
            accent: Colors.orange[800]!, icon: Icons.timer_off_rounded,
            label: '⛔ EXPIRED Medicine');
      case 'POSSIBLE_MATCH':
        return _StatusTheme(bg: const Color(0xFFFFF8E1),
            accent: Colors.amber[800]!, icon: Icons.warning_amber_rounded,
            label: '⚡ Possible NSQ Match');
      case 'SAFE':
        return _StatusTheme(bg: const Color(0xFFE8F5E9),
            accent: Colors.green[700]!, icon: Icons.check_circle_rounded,
            label: '✅ SAFE — Not in NSQ List');
      default:
        return _StatusTheme(bg: Colors.grey[100]!,
            accent: Colors.grey[700]!, icon: Icons.help_outline_rounded,
            label: '❓ Unknown');
    }
  }
}

// ─────────────────────────────────────────────────────────────
class _StatusTheme {
  final Color bg, accent; final IconData icon; final String label;
  const _StatusTheme(
      {required this.bg, required this.accent,
       required this.icon, required this.label});
}

// ─────────────────────────────────────────────────────────────
// Cross-check summary card
// ─────────────────────────────────────────────────────────────
class _CrossCheckCard extends StatelessWidget {
  final int nameScore;
  final dynamic batchMatched, expiryMatchesDb;
  final bool isExpired;
  const _CrossCheckCard({
    required this.nameScore, required this.batchMatched,
    required this.isExpired, required this.expiryMatchesDb,
  });

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Row(children: [
          Icon(Icons.fact_check, color: Color(0xFF1565C0), size: 18),
          SizedBox(width: 8),
          Text('Cross-Check Results',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold,
                  color: Color(0xFF1A237E))),
        ]),
        const SizedBox(height: 12),
        _ChkRow(
          label: 'Batch number (primary)',
          icon: batchMatched == true  ? Icons.dangerous_rounded
              : batchMatched == false ? Icons.check_rounded
              : Icons.remove_rounded,
          color: batchMatched == true  ? Colors.red
              : batchMatched == false  ? Colors.green[700]!
              : Colors.grey,
          detail: batchMatched == true  ? '🚨 Found in NSQ database'
              : batchMatched == false   ? '✅ Not in NSQ database'
              : 'Not provided',
        ),
        const SizedBox(height: 7),
        _ChkRow(
          label: 'Drug name (fuzzy)',
          icon: nameScore >= 65 ? Icons.close_rounded
              : nameScore >= 45 ? Icons.help_outline
              : Icons.check_rounded,
          color: nameScore >= 65 ? Colors.red
              : nameScore >= 45 ? Colors.amber[700]!
              : Colors.green[700]!,
          detail: nameScore >= 65 ? 'Found in NSQ list ($nameScore%)'
              : nameScore >= 45   ? 'Possible match ($nameScore%)'
              : nameScore > 0     ? 'Not in NSQ list ($nameScore%)'
              : 'Not in NSQ list',
        ),
        const SizedBox(height: 7),
        _ChkRow(
          label: 'Expiry date',
          icon: isExpired ? Icons.close_rounded : Icons.check_rounded,
          color: isExpired ? Colors.orange[700]! : Colors.green[700]!,
          detail: isExpired ? 'Medicine is expired' : 'Not expired',
        ),
        const SizedBox(height: 7),
        _ChkRow(
          label: 'Expiry vs NSQ record',
          icon: expiryMatchesDb == true  ? Icons.check_rounded
              : expiryMatchesDb == false ? Icons.warning_amber_rounded
              : Icons.remove_rounded,
          color: expiryMatchesDb == true  ? Colors.green[700]!
              : expiryMatchesDb == false  ? Colors.orange[700]!
              : Colors.grey,
          detail: expiryMatchesDb == true  ? 'Matches NSQ record'
              : expiryMatchesDb == false   ? 'Differs from NSQ record'
              : 'Not checked',
        ),
      ]),
    ),
  );
}

class _ChkRow extends StatelessWidget {
  final String label, detail; final IconData icon; final Color color;
  const _ChkRow({required this.label, required this.detail,
      required this.icon, required this.color});

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Container(
        width: 24, height: 24,
        decoration: BoxDecoration(
            color: color.withOpacity(0.12), shape: BoxShape.circle),
        child: Icon(icon, color: color, size: 15),
      ),
      const SizedBox(width: 10),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 12,
                fontWeight: FontWeight.bold, color: Color(0xFF1A237E))),
            Text(detail, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
          ])),
    ],
  );
}

// ─────────────────────────────────────────────────────────────
class _AlertBanner extends StatelessWidget {
  final IconData icon; final Color color, bgColor;
  final String title, body;
  const _AlertBanner({required this.icon, required this.color,
      required this.bgColor, required this.title, required this.body});

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: bgColor,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: color.withOpacity(0.4)),
    ),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: color, size: 22),
      const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TextStyle(color: color,
                fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(height: 4),
            Text(body, style: TextStyle(color: color.withOpacity(0.85),
                fontSize: 12, height: 1.5)),
          ])),
    ]),
  );
}

// ─────────────────────────────────────────────────────────────
class _Section extends StatelessWidget {
  final IconData icon; final String title; final List<_InfoRow> rows;
  const _Section({required this.icon, required this.title, required this.rows});

  @override
  Widget build(BuildContext context) {
    final visible = rows.where((r) =>
        r.value != null && r.value!.isNotEmpty &&
        r.value != 'null' && r.value != 'Not detected' &&
        r.value != 'Not provided').toList();
    if (visible.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, color: const Color(0xFF1565C0), size: 18),
            const SizedBox(width: 8),
            Text(title, style: const TextStyle(fontSize: 14,
                fontWeight: FontWeight.bold, color: Color(0xFF1A237E))),
          ]),
          const Divider(height: 16),
          ...visible,
        ]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
class _InfoRow extends StatelessWidget {
  final String label; final String? value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    if (value == null || value!.isEmpty || value == 'null' ||
        value == 'Not detected' || value == 'Not provided')
      return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 110,
          child: Text(label, style: TextStyle(fontSize: 12,
              color: Colors.grey[600], fontWeight: FontWeight.w500))),
        const Text(' : ', style: TextStyle(color: Colors.grey, fontSize: 12)),
        Expanded(child: Text(value!, style: const TextStyle(fontSize: 12,
            fontWeight: FontWeight.w600, color: Color(0xFF1A237E)))),
      ]),
    );
  }
}
