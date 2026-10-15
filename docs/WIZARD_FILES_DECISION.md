# Owner-files browser fork: bounded adoption decision

Status: owner-approved direction; staged candidate, canonical slot activation awaits
independent storage-boundary review. No public catalog/default change in this PR.

## Decision

Keep the approved Files interface, but split its responsibilities:

- **Wizard Files** is the managed owner-files browser. Package identity `wizard-files`;
  it reads only `${ROOT_FOLDER_HOST}/media`, matching `docs/SYSTEM_APPS.md` on main.
- **Files Legacy** preserves the prior custom application and integrations under its
  own launcher identity, `files-legacy`. It is not a data source of Wizard Files.
- Existing contents of `media/` stay where they are. Their presence is not endorsement
  of their current taxonomy. No content migration, imports or reorganization is approved.
- The proposed filesystem layout on `proposal/app-standard-views-layout` is not adopted
  by this decision. In particular, no Meditate or Wisdom relocation follows from it.

## Candidate contract

The clean code-only repository is `humanitylabs-org/wizard-files` (private). It reuses
the approved visual layer and shared WizardApp services, but not the legacy aggregator,
source indexes, private-app catalog, host scanners, or private-agent storage.

The runtime has one read-only owner-files bind, no application data database and no
legacy mounts. File opens walk descriptor-relative components with no-follow checks;
traversal, symlinks, hidden paths and special files are rejected. Search, preview and
download use this same root. Active file formats are downloads, not trusted app code.

Uploads use the existing system resumable transfer service; there is no second uploader
backend or arbitrary whole-file cap. That service must be configured to complete shared
owner uploads into the same media root. Private-agent delivery remains separate.

WAM installs the private package and persists its lifecycle and registry. Host staging
may project the package under `wizard-files-next` without claiming the canonical files
slot. Following review, the canonical entry becomes Wizard Files and the previous entry
becomes Files Legacy. A source/image/route receipt and rollback are required.

## Ownership

The app fork and per-box adoption are approved. Universal defaults in App Manager remain
owned by the App Manager maintainer: any default change is a separate proposal, not an
implicit consequence of this PR. Public catalog publication requires separate approval.
Web-app adoption does not require an APK or VM guest rebuild; include it at the next
significant guest release via the adoption queue.
