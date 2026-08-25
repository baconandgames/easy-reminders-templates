import EventKit
import Foundation

struct CreatePayload: Decodable {
	let listIdentifier: String?
	let listName: String
	let items: [String]
}

struct ListCompletedPayload: Decodable {
	let listIdentifier: String
	let days: Int?
}

struct CompletedReminderItem: Encodable {
	let title: String
	let completionDate: String?

	enum CodingKeys: String, CodingKey {
		case title
		case completionDate = "completion_date"
	}
}

struct ReminderTarget: Encodable {
	let id: String
	let name: String
	let source: String
	let itemCount: Int
	let sampleItems: [String]

	enum CodingKeys: String, CodingKey {
		case id
		case name
		case source
		case itemCount = "item_count"
		case sampleItems = "sample_items"
	}
}

func fail(_ message: String, code: Int32 = 1) -> Never {
	FileHandle.standardError.write(Data((message + "\n").utf8))
	exit(code)
}

func requestReminderAccess(_ store: EKEventStore) {
	let semaphore = DispatchSemaphore(value: 0)
	var grantedAccess = false
	var accessError: Error?

	store.requestAccess(to: .reminder) { granted, error in
		grantedAccess = granted
		accessError = error
		semaphore.signal()
	}

	semaphore.wait()

	if let accessError {
		fail("Reminders access failed: \(accessError.localizedDescription)")
	}

	if !grantedAccess {
		fail("Reminders access was not granted.")
	}
}

func reminderCalendars(in store: EKEventStore) -> [EKCalendar] {
	store.calendars(for: .reminder)
		.sorted { lhs, rhs in
			lhs.title.localizedCaseInsensitiveCompare(rhs.title) == .orderedAscending
		}
}

func findCalendar(in store: EKEventStore, identifier: String?, name: String) -> EKCalendar? {
	let calendars = reminderCalendars(in: store)

	if let identifier, !identifier.isEmpty {
		if let calendar = calendars.first(where: { $0.calendarIdentifier == identifier }) {
			return calendar
		}
	}

	return calendars.first(where: { $0.title == name })
}

func listReminders(in store: EKEventStore) {
	for calendar in reminderCalendars(in: store) {
		print("\(calendar.title)\t\(calendar.calendarIdentifier)\t\(calendar.source.title)")
	}
}

func incompleteReminderTitles(in store: EKEventStore, calendar: EKCalendar) -> [String] {
	let semaphore = DispatchSemaphore(value: 0)
	let predicate = store.predicateForIncompleteReminders(
		withDueDateStarting: nil,
		ending: nil,
		calendars: [calendar]
	)
	var titles: [String] = []

	store.fetchReminders(matching: predicate) { reminders in
		titles = (reminders ?? [])
			.map { $0.title ?? "" }
			.filter { !$0.isEmpty }
		semaphore.signal()
	}

	semaphore.wait()
	return titles
}

func completedReminderItems(in store: EKEventStore, calendar: EKCalendar, days: Int?) -> [CompletedReminderItem] {
	let semaphore = DispatchSemaphore(value: 0)
	let startDate: Date?
	if let days, days > 0 {
		startDate = Calendar.current.date(byAdding: .day, value: -days, to: Date())
	} else {
		startDate = nil
	}
	let predicate = store.predicateForCompletedReminders(
		withCompletionDateStarting: startDate,
		ending: nil,
		calendars: [calendar]
	)
	let dateFormatter = ISO8601DateFormatter()
	var items: [CompletedReminderItem] = []

	store.fetchReminders(matching: predicate) { reminders in
		items = (reminders ?? [])
			.compactMap { reminder in
				guard let title = reminder.title?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty else {
					return nil
				}
				let completionDate = reminder.completionDate.map { dateFormatter.string(from: $0) }
				return CompletedReminderItem(title: title, completionDate: completionDate)
			}
			.sorted { lhs, rhs in
				(lhs.completionDate ?? "") > (rhs.completionDate ?? "")
			}
		semaphore.signal()
	}

	semaphore.wait()
	return items
}

func listTargets(in store: EKEventStore) {
	let targets = reminderCalendars(in: store).map { calendar in
		let titles = incompleteReminderTitles(in: store, calendar: calendar)
		return ReminderTarget(
			id: calendar.calendarIdentifier,
			name: calendar.title,
			source: calendar.source.title,
			itemCount: titles.count,
			sampleItems: Array(titles.prefix(3))
		)
	}

	do {
		let data = try JSONEncoder().encode(targets)
		guard let output = String(data: data, encoding: .utf8) else {
			fail("Could not encode reminder targets.")
		}
		print(output)
	} catch {
		fail("Could not encode reminder targets: \(error.localizedDescription)")
	}
}

func listItems(in store: EKEventStore) {
	let input = FileHandle.standardInput.readDataToEndOfFile()
	guard let listIdentifier = String(data: input, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
		!listIdentifier.isEmpty else {
		fail("Reminder list identifier must not be empty.")
	}

	guard let calendar = reminderCalendars(in: store).first(where: { $0.calendarIdentifier == listIdentifier }) else {
		fail("Reminder list not found: \(listIdentifier)")
	}

	let titles = incompleteReminderTitles(in: store, calendar: calendar)

	do {
		let data = try JSONEncoder().encode(titles)
		guard let output = String(data: data, encoding: .utf8) else {
			fail("Could not encode reminder items.")
		}
		print(output)
	} catch {
		fail("Could not encode reminder items: \(error.localizedDescription)")
	}
}

func listCompletedItems(in store: EKEventStore) {
	let input = FileHandle.standardInput.readDataToEndOfFile()
	let payload: ListCompletedPayload

	do {
		payload = try JSONDecoder().decode(ListCompletedPayload.self, from: input)
	} catch {
		fail("Invalid completed reminder payload: \(error.localizedDescription)")
	}

	guard !payload.listIdentifier.isEmpty else {
		fail("Reminder list identifier must not be empty.")
	}

	guard let calendar = reminderCalendars(in: store).first(where: { $0.calendarIdentifier == payload.listIdentifier }) else {
		fail("Reminder list not found: \(payload.listIdentifier)")
	}

	let items = completedReminderItems(in: store, calendar: calendar, days: payload.days)

	do {
		let data = try JSONEncoder().encode(items)
		guard let output = String(data: data, encoding: .utf8) else {
			fail("Could not encode completed reminder items.")
		}
		print(output)
	} catch {
		fail("Could not encode completed reminder items: \(error.localizedDescription)")
	}
}

func createList(in store: EKEventStore) {
	let input = FileHandle.standardInput.readDataToEndOfFile()
	guard let listName = String(data: input, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
		!listName.isEmpty else {
		fail("Reminder list name must not be empty.")
	}

	guard let source = store.defaultCalendarForNewReminders()?.source ?? store.sources.first else {
		fail("Could not find an Apple Reminders account.")
	}

	let calendar = EKCalendar(for: .reminder, eventStore: store)
	calendar.title = listName
	calendar.source = source

	do {
		try store.saveCalendar(calendar, commit: true)
	} catch {
		fail("Could not create reminder list \"\(listName)\": \(error.localizedDescription)")
	}

	let target = ReminderTarget(
		id: calendar.calendarIdentifier,
		name: calendar.title,
		source: calendar.source.title,
		itemCount: 0,
		sampleItems: []
	)

	do {
		let data = try JSONEncoder().encode(target)
		guard let output = String(data: data, encoding: .utf8) else {
			fail("Could not encode created reminder target.")
		}
		print(output)
	} catch {
		fail("Could not encode created reminder target: \(error.localizedDescription)")
	}
}

func createReminders(in store: EKEventStore) {
	let input = FileHandle.standardInput.readDataToEndOfFile()
	let payload: CreatePayload

	do {
		payload = try JSONDecoder().decode(CreatePayload.self, from: input)
	} catch {
		fail("Invalid create payload: \(error.localizedDescription)")
	}

	guard let calendar = findCalendar(in: store, identifier: payload.listIdentifier, name: payload.listName) else {
		fail("Reminder list not found: \(payload.listName)")
	}

	for item in payload.items {
		let reminder = EKReminder(eventStore: store)
		reminder.title = item
		reminder.calendar = calendar

		do {
			try store.save(reminder, commit: false)
		} catch {
			fail("Could not save reminder \"\(item)\": \(error.localizedDescription)")
		}
	}

	do {
		try store.commit()
	} catch {
		fail("Could not commit reminders: \(error.localizedDescription)")
	}
}

let arguments = CommandLine.arguments
guard arguments.count == 2 else {
	fail("Usage: reminders-helper.swift <list-reminders|list-targets|list-items|list-completed-items|create-list|create-reminders>")
}

let store = EKEventStore()
requestReminderAccess(store)

switch arguments[1] {
case "list-reminders":
	listReminders(in: store)
case "list-targets":
	listTargets(in: store)
case "list-items":
	listItems(in: store)
case "list-completed-items":
	listCompletedItems(in: store)
case "create-list":
	createList(in: store)
case "create-reminders":
	createReminders(in: store)
default:
	fail("Unknown command: \(arguments[1])")
}
