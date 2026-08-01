<?php

namespace App\Http\Controllers;

use App\Custom\DatabookAPI;
use Illuminate\Http\Request;

/**
 * The org register's editing UI — Phase 5's second half.
 *
 * A PURE CONSUMER of /admin/orgs (api/routers/org_admin.py). Every invariant —
 * the type vocabulary, the rename confirmation, cycle rejection,
 * retirement-not-deletion, unknown-field rejection — is enforced by the API and
 * deliberately NOT re-implemented here. This layer's job is to surface the
 * refusals in a form a human can act on.
 *
 * ⚠ That split is the point. Re-checking a rule here would mean two copies that
 * can disagree, and the API's copy is the one that also governs curl and bulk
 * scripts. So when the API answers 409 "needs confirm_rename", this page shows
 * the reason and the blast radius and offers the confirmation — it does not
 * decide for itself whether a rename is safe.
 *
 * ⚠⚠ AUTHENTICATION IS NOT IN THIS FILE, AND THAT IS A DELIBERATE, DOCUMENTED
 * CHOICE. The Laravel app has no user system: everything under /about/* is
 * public by design, and there is no session, guard or middleware to hang an
 * editor role on. Building one here would duplicate the auth the API already
 * has. So the gate is nginx basic auth on /admin/ at the ORIGIN — the same
 * control Phase 0 used for the normalizer, for the same reason: task dda13bf3
 * records that the origin answers direct connections, so a Cloudflare-layer
 * policy would be bypassable.
 *
 * See nginx/conf.d/ssl.conf and scripts/org-admin-auth-setup.sh. If that gate
 * is ever removed, this becomes an unauthenticated write surface onto the
 * register — exactly the Phase 0 finding, repeated.
 */
class OrgAdmin extends Controller
{
	/** Searchable list of orgs to edit. */
	public function index(Request $request)
	{
		$q = trim((string)$request->query('q', ''));
		// The directory endpoint already excludes retired rows and is cached by
		// the browser; filtering client-side keeps this page dependency-free.
		$orgs = DatabookAPI::req('/get/orgs/all') ?: [];
		// Embedded rather than fetched: one fewer request, one fewer failure
		// mode, and the page still cannot invent a type.
		list($vstatus, $vocab) = DatabookAPI::adminReq('/admin/orgs/vocabulary');

		return view('admin.orgs.index', [
			'orgs' => $orgs,
			'types' => ($vstatus === 200 ? ($vocab['types'] ?? []) : []),
			'q' => $q,
			'editor' => $this->actor($request),
			'pagetitle' => 'Org register | Admin',
		]);
	}

	/** The edit form for one org. */
	public function edit(Request $request, $id)
	{
		list($status, $body) = DatabookAPI::adminReq('/admin/orgs/' . (int)$id);
		if ($status === 404)
			abort(404);
		if ($status !== 200)
			return view('admin.orgs.unavailable', [
				'status' => $status,
				'detail' => $body['detail'] ?? null,
				'pagetitle' => 'Org register | Admin',
			]);

		list($vstatus, $vocab) = DatabookAPI::adminReq('/admin/orgs/vocabulary');

		return view('admin.orgs.edit', [
			'org' => $body['org'] ?? [],
			'audit' => $body['audit'] ?? [],
			'renameImpact' => $body['rename_impact'] ?? [],
			'editableFields' => $body['editable_fields'] ?? [],
			'types' => ($vstatus === 200 ? ($vocab['types'] ?? []) : []),
			'orgs' => DatabookAPI::req('/get/orgs/all') ?: [],
			'editor' => $this->actor($request),
			'pagetitle' => ($body['org']['name'] ?? 'Org') . ' | Admin',
		]);
	}

	/**
	 * Proxy a mutation to the API and hand the verdict back as JSON.
	 *
	 * The page's JS renders whatever comes back, including the refusals — a 409
	 * carries the reason and the contract count, and the human decides.
	 */
	public function save(Request $request, $id)
	{
		return $this->proxy('/admin/orgs/' . (int)$id, 'patch', $request);
	}

	public function create(Request $request)
	{
		return $this->proxy('/admin/orgs', 'post', $request);
	}

	public function retire(Request $request, $id)
	{
		return $this->proxy('/admin/orgs/' . (int)$id . '/retire', 'post', $request);
	}

	public function unretire(Request $request, $id)
	{
		return $this->proxy('/admin/orgs/' . (int)$id . '/unretire', 'post', $request);
	}

	private function proxy($uri, $method, Request $request)
	{
		$payload = $request->json()->all();
		if (!is_array($payload) || !$payload)
			$payload = $request->except(['_token']);
		// ⚠ The payload is passed THROUGH, not whitelisted here. The API rejects
		// unknown fields with a 400 that names them; re-filtering would silently
		// drop a typo instead, which is the failure mode the API's rule exists
		// to prevent.
		list($status, $body) = DatabookAPI::adminReq($uri, $method, $payload);
		return response()->json($body ?? [], $status ?: 502);
	}

	/**
	 * Who is editing, per the origin's basic-auth gate.
	 *
	 * ⚠ Shown so the person can SEE which identity the audit trail will record.
	 * It is not an authorization decision — nginx already made that. The API
	 * attributes the change to the token's user, which is the durable record;
	 * this is only the label on screen.
	 */
	private function actor(Request $request)
	{
		return $request->server('PHP_AUTH_USER')
			?: $request->server('REMOTE_USER')
			?: null;
	}
}
